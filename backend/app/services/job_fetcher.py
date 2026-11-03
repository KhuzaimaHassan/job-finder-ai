"""Shared job snapshot, persistence and query policy. Providers live in job_sources."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import re
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from app.config import settings
from app.schemas.jobs import Job
from app.services.job_normalization import contains_skill, plain_text
from app.services.db_retry import db_call
from app.services.job_policy import searchable, parse_date, query_score, relevant_role
from app.services.job_sources import (fetch_adzuna_jobs, fetch_remoteok_jobs, fetch_remotive_jobs,
    fetch_himalayas_jobs, fetch_jobicy_jobs, _parse_himalayas_job)

logger = logging.getLogger(__name__)
_job_store: dict[str, Job] = {}
_cache_loaded = False
_refresh_finished = False
_snapshot_task: asyncio.Task | None = None
_last_snapshot_load = 0.0
SNAPSHOT_PAGE_SIZE = 200

KNOWN_TAGS = ['Python', 'Machine Learning', 'Data Science', 'AI', 'Deep Learning', 'TensorFlow', 'PyTorch', 'Scikit-learn', 'NLP', 'Computer Vision', 'SQL', 'Pandas', 'NumPy', 'FastAPI', 'Django', 'Flask', 'Docker', 'AWS', 'GCP', 'Azure', 'React', 'Node.js', 'JavaScript', 'TypeScript', 'Spark', 'Airflow', 'Power BI', 'Tableau', 'R', 'HuggingFace', 'LLM', 'GPT', 'Transformer', 'Statistics', 'MLOps', 'ETL', 'Data Engineering', 'Streamlit', 'Kubernetes', 'Java', 'Go', 'Rust', 'C++']
_TAG_NAMES = {tag.lower(): tag for tag in KNOWN_TAGS if tag not in ("R", "Go")}
_TAG_PATTERN = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(tag) for tag in _TAG_NAMES) + r")(?!\w)", re.I)
PAKISTAN_LOCATIONS = {'sargodha', 'lahore', 'abbottabad', 'mardan', 'bahawalpur', 'faisalabad', 'islamabad', 'sialkot', 'hyderabad, pakistan', 'peshawar', 'pakistan', 'rawalpindi', 'karachi', 'multan', 'gujranwala', 'quetta'}


def _get_supabase_client():
    from app.services.supabase_client import get_supabase
    return get_supabase()


def _extract_tags(text):
    text = plain_text(text)
    found = {_TAG_NAMES[match.group().lower()] for match in _TAG_PATTERN.finditer(text)}
    for tag in ("R", "Go"):
        if contains_skill(text, tag, normalized=True):
            found.add(tag)
    return [tag for tag in KNOWN_TAGS if tag in found][:10]


def _job_from_row(row):
    payload = {key: row[key] for key in Job.model_fields if key in row}
    payload["description"] = (payload.get("description") or "")[:10000]
    for key in ("tags", "location_restrictions", "timezone_restrictions"):
        payload[key] = payload.get(key) or []
    payload["posted_date"] = parse_date(row.get("posted_date")).isoformat() if parse_date(row.get("posted_date")) else None
    payload["tags"] = _extract_tags(f"{row.get('title', '')} {payload['description']}")
    return Job(**payload)


def _is_relevant_job(job):
    if not relevant_role(job):
        return False
    return job.job_type == "remote" or (not job.job_type and job.location.lower() in ("remote", "worldwide", "anywhere")) or any(place in job.location.lower() for place in PAKISTAN_LOCATIONS)


def _load_persisted_jobs():
    client = _get_supabase_client()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=settings.JOB_CACHE_MAX_AGE_DAYS)).isoformat()
    # posted_date is a legacy text column with both date-only and ISO values.
    # Use inclusive date bounds here, then enforce exact instants in searchable.
    posted_cutoff = (now - timedelta(days=settings.JOB_POSTED_MAX_AGE_DAYS)).date().isoformat()
    jobs = []
    for offset in range(0, 100000, SNAPSHOT_PAGE_SIZE):
        rows = (client.table("jobs").select("*").gte("fetched_at", cutoff)
                .gte("posted_date", posted_cutoff)
                .or_(f"expires_at.is.null,expires_at.gt.{now.isoformat()}")
                .order("id").range(offset, offset + SNAPSHOT_PAGE_SIZE - 1).execute().data or [])
        for row in rows:
            try:
                # Reject stale/closed/legacy rows before HTML/tag processing and
                # Pydantic normalization. Archived records remain in the DB.
                policy = SimpleNamespace(**{key: row.get(key) for key in
                    ("source", "provider_id", "expires_at", "fetched_at", "posted_date", "availability")})
                if not searchable(policy, now):
                    continue
                job = _job_from_row(row)
                if _is_relevant_job(job):
                    jobs.append(job)
            except (ValueError, TypeError):
                logger.warning("Skipped invalid persisted job")
        if len(rows) < SNAPSHOT_PAGE_SIZE:
            return jobs
    raise RuntimeError("Job snapshot load exceeded its safety limit")


async def fetch_jobs_from_supabase():
    return await db_call(_load_persisted_jobs, attempts=3)


def publish_snapshot(jobs):
    global _job_store, _cache_loaded
    # Include location and contract in vacancy identity; source IDs remain stored.
    unique = {}
    now = datetime.now(timezone.utc)
    for job in sorted((job for job in jobs if searchable(job, now)), key=lambda j: (j.posted_date or "", j.id), reverse=True):
        geo = job.location
        if job.job_type == "remote" and geo.lower() in ("remote", "worldwide", "anywhere", "global"):
            geo = "global"
        title = re.sub(r"[,;:–—-]", " ", job.title)
        key = tuple(re.sub(r"\s+", " ", value.lower()).strip() for value in
                    (title, job.company, geo, job.employment_type or "")) + (
                        tuple(sorted(job.location_restrictions)), tuple(sorted(job.timezone_restrictions)))
        unique.setdefault(key, job)
    _job_store = {job.id: job for job in unique.values()}
    _cache_loaded = True


async def _reload_snapshot():
    global _last_snapshot_load
    started = time.monotonic()
    jobs = await fetch_jobs_from_supabase()
    publish_snapshot(jobs)
    _last_snapshot_load = time.monotonic()
    logger.info("Search snapshot loaded: %d jobs in %.2fs", len(_job_store), _last_snapshot_load - started)


async def reload_snapshot(*, force=False):
    global _snapshot_task
    # A timed-out waiter must not release a lock while its to_thread DB work
    # continues. Every waiter shares the same task until that load finishes.
    if _snapshot_task is not None and not _snapshot_task.done():
        return await asyncio.shield(_snapshot_task)
    if not force and _cache_loaded and time.monotonic() - _last_snapshot_load < settings.JOB_SNAPSHOT_RELOAD_SECONDS:
        return
    _snapshot_task = asyncio.create_task(_reload_snapshot())
    # Retrieve failures even if all callers timed out; the next tick can retry.
    _snapshot_task.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
    return await asyncio.shield(_snapshot_task)


def cache_ready():
    return bool(_job_store) or (_cache_loaded and _refresh_finished)


def _persist_jobs(jobs):
    if not jobs:
        return
    client = _get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    for start in range(0, len(jobs), 200):
        batch = []
        for job in jobs[start:start + 200]:
            job.fetched_at = now
            row = job.model_dump(exclude={"is_active", "first_seen_at"})
            row["fetched_at"] = now
            row["description"] = row["description"][:10000]
            batch.append(row)
        client.table("jobs").upsert(batch, on_conflict="id").execute()


async def persist_jobs_to_supabase(jobs):
    # Upsert by provider ID is safe to repeat after a lost response.
    await db_call(lambda: _persist_jobs(jobs), attempts=3)


async def fetch_all_jobs():
    from app.services.ingestion import refresh_jobs
    return await refresh_jobs()


def get_all_jobs():
    return [job for job in _job_store.values() if searchable(job) and _is_relevant_job(job)]


def get_job_by_id(job_id):
    job = _job_store.get(job_id)
    return job if job and searchable(job) else None


async def get_archived_job_by_id(job_id):
    def load():
        rows = _get_supabase_client().table("jobs").select("*").eq("id", job_id).limit(1).execute().data
        return _job_from_row(rows[0]).model_copy(update={"is_active": False}) if rows else None
    try:
        return await asyncio.to_thread(load)
    except Exception:
        logger.exception("Archived job lookup failed")
        return None


def search_jobs(q=None, location=None, job_type=None, source=None, page=1, per_page=20, employment_type=None, posted_within_days=None):
    jobs = get_all_jobs()
    if posted_within_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=posted_within_days)
        jobs = [job for job in jobs if parse_date(job.posted_date) and parse_date(job.posted_date) >= cutoff]
    if q and q.strip():
        jobs = [job for job in jobs if query_score(job, q) > 0]
    if location:
        loc = location.lower().strip()
        if loc == "remote":
            jobs = [job for job in jobs if job.job_type == "remote"]
        elif loc in ("pakistan", "pk"):
            jobs = [job for job in jobs if any(place in job.location.lower() for place in PAKISTAN_LOCATIONS)]
        else:
            jobs = [job for job in jobs if loc in job.location.lower()]
    if job_type:
        kind = re.sub(r"[\s_-]", "", job_type.lower())
        if kind in ("remote", "onsite", "hybrid"):
            jobs = [job for job in jobs if job.job_type == kind]
        elif kind in ("fulltime", "parttime", "internship", "contract"):
            employment_type = kind
    if employment_type:
        kind = re.sub(r"[\s_-]", "", employment_type.lower())
        jobs = [job for job in jobs if job.employment_type == kind]
    if source:
        jobs = [job for job in jobs if job.source == source.lower()]
    jobs.sort(key=lambda job: (-(query_score(job, q) if q else 0),
        -(parse_date(job.posted_date).timestamp() if parse_date(job.posted_date) else 0), job.id))
    start = (page - 1) * per_page
    return jobs[start:start + per_page], len(jobs)
