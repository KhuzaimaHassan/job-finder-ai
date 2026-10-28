"""Shared job snapshot, persistence and query policy. Providers live in job_sources."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import re
from urllib.parse import urlsplit

from app.config import settings
from app.schemas.jobs import Job
from app.services.job_normalization import contains_skill
from app.services.job_policy import searchable, parse_date, query_score, relevant_role
from app.services.job_sources import (fetch_adzuna_jobs, fetch_remoteok_jobs, fetch_remotive_jobs,
    fetch_himalayas_jobs, fetch_jobicy_jobs, _parse_himalayas_job)

logger = logging.getLogger(__name__)
_job_store: dict[str, Job] = {}
_cache_loaded = False
_refresh_finished = False
_load_lock = asyncio.Lock()

KNOWN_TAGS = ['Python', 'Machine Learning', 'Data Science', 'AI', 'Deep Learning', 'TensorFlow', 'PyTorch', 'Scikit-learn', 'NLP', 'Computer Vision', 'SQL', 'Pandas', 'NumPy', 'FastAPI', 'Django', 'Flask', 'Docker', 'AWS', 'GCP', 'Azure', 'React', 'Node.js', 'JavaScript', 'TypeScript', 'Spark', 'Airflow', 'Power BI', 'Tableau', 'R', 'HuggingFace', 'LLM', 'GPT', 'Transformer', 'Statistics', 'MLOps', 'ETL', 'Data Engineering', 'Streamlit', 'Kubernetes', 'Java', 'Go', 'Rust', 'C++']
PAKISTAN_LOCATIONS = {'sargodha', 'lahore', 'abbottabad', 'mardan', 'bahawalpur', 'faisalabad', 'islamabad', 'sialkot', 'hyderabad, pakistan', 'peshawar', 'pakistan', 'rawalpindi', 'karachi', 'multan', 'gujranwala', 'quetta'}


def _get_supabase_client():
    from app.services.supabase_client import get_supabase
    return get_supabase()


def _extract_tags(text):
    return [tag for tag in KNOWN_TAGS if contains_skill(text, tag)][:10]


def _job_from_row(row):
    payload = {key: row[key] for key in Job.model_fields if key in row}
    for key in ("tags", "location_restrictions", "timezone_restrictions"):
        payload[key] = payload.get(key) or []
    payload["posted_date"] = parse_date(row.get("posted_date")).isoformat() if parse_date(row.get("posted_date")) else None
    payload["tags"] = _extract_tags(f"{row.get('title', '')} {row.get('description', '')}")
    return Job(**payload)


def _is_relevant_job(job):
    if not relevant_role(job):
        return False
    return job.job_type == "remote" or (not job.job_type and job.location.lower() in ("remote", "worldwide", "anywhere")) or any(place in job.location.lower() for place in PAKISTAN_LOCATIONS)


def _load_persisted_jobs():
    client = _get_supabase_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.JOB_CACHE_MAX_AGE_DAYS)).isoformat()
    jobs = []
    for offset in range(0, 100000, 1000):
        rows = client.table("jobs").select("*").gte("fetched_at", cutoff).order("id").range(offset, offset + 999).execute().data or []
        for row in rows:
            try:
                job = _job_from_row(row)
                if _is_relevant_job(job):
                    jobs.append(job)
            except (ValueError, TypeError):
                logger.warning("Skipped invalid persisted job")
        if len(rows) < 1000:
            return jobs
    raise RuntimeError("Job snapshot load exceeded its safety limit")


async def fetch_jobs_from_supabase():
    return await asyncio.to_thread(_load_persisted_jobs)


def publish_snapshot(jobs):
    global _job_store, _cache_loaded
    # Include location and contract in vacancy identity; source IDs remain stored.
    unique = {}
    for job in sorted(jobs, key=lambda j: (j.posted_date or "", j.id), reverse=True):
        key = tuple(re.sub(r"\s+", " ", value.lower()).strip() for value in
                    (job.title, job.company, job.location, job.employment_type or ""))
        unique.setdefault(key, job)
    _job_store = {job.id: job for job in unique.values()}
    _cache_loaded = True


async def reload_snapshot():
    async with _load_lock:
        jobs = await fetch_jobs_from_supabase()
        publish_snapshot(jobs)


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
    await asyncio.to_thread(_persist_jobs, jobs)


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
