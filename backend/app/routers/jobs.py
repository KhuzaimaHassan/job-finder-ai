import asyncio
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas.jobs import Job, JobSearchResponse
from app.services.job_fetcher import search_jobs, get_job_by_id, get_all_jobs, get_archived_job_by_id
from app.services.auth import get_current_user
from app.services.supabase_client import get_user_supabase
from app.services.job_fetcher import cache_ready
from app.services.ingestion import status as ingestion_status
from app.services.embeddings import rank_jobs_for_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _decode_supabase_json_columns(row: dict) -> dict:
    """Turn JSON/array columns that arrive as strings into Python lists/objects."""
    out = dict(row)
    for key in ("skills", "target_roles", "experience", "education", "projects"):
        val = out.get(key)
        if isinstance(val, str) and val.strip().startswith(("[", "{")):
            try:
                out[key] = json.loads(val)
            except json.JSONDecodeError:
                pass
    return out


def _matched_job_payload(job: Any, match_score: float, match_method: str = "keyword") -> dict:
    """JSON-serializable dict for the matched-jobs response."""
    if hasattr(job, "model_dump"):
        payload = job.model_dump(mode="json")
    elif isinstance(job, dict):
        payload = dict(job)
    else:
        raise TypeError(f"Unexpected job type: {type(job)!r}")
    payload["match_score"] = float(match_score)
    payload["match_method"] = match_method
    return payload


def require_ready():
    if not cache_ready():
        raise HTTPException(503, "Job listings are warming up. Please retry shortly.", headers={"Retry-After": "5"})


@router.get("/status")
def job_ingestion_status():
    return ingestion_status()


@router.get("", response_model=JobSearchResponse)
def list_jobs(
    q: Optional[str] = Query(None, max_length=200, description="Search keyword"),
    location: Optional[str] = Query(None, description="Location filter (e.g. 'remote', 'karachi')"),
    job_type: Optional[str] = Query(None, description="Job type: remote, fulltime, parttime, internship"),
    source: Optional[str] = Query(None, description="Source: adzuna, remoteok, remotive"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    employment_type: Optional[str] = Query(None, description="fulltime, parttime, internship, contract"),
    posted_within_days: Optional[int] = Query(None, ge=1, le=365),
):
    """Search and filter jobs with pagination."""
    require_ready()
    jobs, total = search_jobs(
        q=q,
        location=location,
        job_type=job_type,
        source=source,
        page=page,
        per_page=per_page,
        employment_type=employment_type, posted_within_days=posted_within_days,
    )
    return JobSearchResponse(
        jobs=jobs,
        total=total,
        page=page,
        per_page=per_page,
        has_more=(page * per_page) < total,
    )


@router.get("/search", response_model=JobSearchResponse)
def search_jobs_endpoint(
    q: Optional[str] = Query(None, max_length=200, description="Search keyword"),
    location: Optional[str] = Query(None, description="Location filter"),
    type: Optional[str] = Query(None, alias="type", description="Job type filter"),
    source: Optional[str] = Query(None, description="Source filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    employment_type: Optional[str] = Query(None),
    posted_within_days: Optional[int] = Query(None, ge=1, le=365),
):
    """Alternative search endpoint with 'type' alias."""
    require_ready()
    jobs, total = search_jobs(
        q=q,
        location=location,
        job_type=type,
        source=source,
        page=page,
        per_page=per_page,
        employment_type=employment_type, posted_within_days=posted_within_days,
    )
    return JobSearchResponse(
        jobs=jobs,
        total=total,
        page=page,
        per_page=per_page,
        has_more=(page * per_page) < total,
    )


@router.get("/stats")
def job_stats():
    """Return quick stats about the cached jobs."""
    require_ready()
    all_jobs = get_all_jobs()
    sources: dict[str, int] = {}
    remote_count = 0
    for j in all_jobs:
        sources[j.source] = sources.get(j.source, 0) + 1
        if j.job_type == "remote":
            remote_count += 1
    return {
        "total_jobs": len(all_jobs),
        "by_source": sources,
        "remote_jobs": remote_count,
    }


@router.get("/matched")
async def matched_jobs(
    q: Optional[str] = Query(None, max_length=200),
    location: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    employment_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    posted_within_days: Optional[int] = Query(None, ge=1, le=365),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """
    Return jobs ranked by match score to the current user's profile/resume.
    Requires authentication.
    """
    require_ready()
    def load_context():
        supabase = get_user_supabase(user["token"])
        profiles = supabase.table("profiles").select("*").eq("user_id", user["id"]).execute().data
        resumes = supabase.table("resumes").select("*").eq("user_id", user["id"]).order("parsed_at", desc=True).limit(1).execute().data
        return (_decode_supabase_json_columns(profiles[0]) if profiles else {},
                _decode_supabase_json_columns(resumes[0]) if resumes else None)
    try:
        profile, resume = await asyncio.to_thread(load_context)
    except Exception as exc:
        logger.exception("Could not load matching context")
        raise HTTPException(503, "Could not load your profile and resume. Please retry.") from exc

    if not profile.get("skills") and not profile.get("target_roles") and not resume:
        raise HTTPException(
            status_code=400,
            detail="Upload a resume or add skills to your profile first",
        )

    # Get all jobs and rank them
    all_jobs_list, _ = await asyncio.to_thread(search_jobs, q=q, location=location, job_type=job_type, source=source,
                                              employment_type=employment_type, posted_within_days=posted_within_days, per_page=100000)
    try:
        ranked = await rank_jobs_for_user(
            user_id=user["id"],
            profile=profile,
            resume=resume,
            jobs=all_jobs_list,
            top_n=200,
        )
    except Exception as e:
        logger.exception("Matching error")
        raise HTTPException(status_code=500, detail="Matching failed due to internal error") from e

    # Paginate
    total = len(ranked)
    start = (page - 1) * per_page
    page_items = ranked[start : start + per_page]

    try:
        job_payloads = [
            {**_matched_job_payload(item["job"], item["match_score"], item.get("match_method", "keyword")),
             "matching_skills": item.get("matching_skills", []), "match_reasons": item.get("match_reasons", [])}
            for item in page_items
        ]
    except Exception as e:
        logger.exception("Failed to serialize matched jobs response")
        raise HTTPException(
            status_code=500,
            detail="Could not build response format",
        ) from e

    return {
        "jobs": job_payloads,
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_more": (page * per_page) < total,
    }


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str):
    """Get a single job by ID."""
    job = get_job_by_id(job_id) or await get_archived_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
