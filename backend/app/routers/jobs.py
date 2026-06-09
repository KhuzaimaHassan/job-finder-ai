import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.schemas import Job, JobSearchResponse
from app.services.job_fetcher import search_jobs, get_job_by_id, get_all_jobs
from app.services.auth import get_current_user
from app.services.supabase_client import get_supabase
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


def _matched_job_payload(job: Any, match_score: float) -> dict:
    """JSON-serializable dict for the matched-jobs response."""
    if hasattr(job, "model_dump"):
        payload = job.model_dump(mode="json")
    elif isinstance(job, dict):
        payload = dict(job)
    else:
        raise TypeError(f"Unexpected job type: {type(job)!r}")
    payload["match_score"] = float(match_score)
    return payload


@router.get("", response_model=JobSearchResponse)
async def list_jobs(
    q: Optional[str] = Query(None, description="Search keyword"),
    location: Optional[str] = Query(None, description="Location filter (e.g. 'remote', 'karachi')"),
    job_type: Optional[str] = Query(None, description="Job type: remote, fulltime, parttime, internship"),
    source: Optional[str] = Query(None, description="Source: adzuna, remoteok, remotive"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
):
    """Search and filter jobs with pagination."""
    jobs, total = search_jobs(
        q=q,
        location=location,
        job_type=job_type,
        source=source,
        page=page,
        per_page=per_page,
    )
    return JobSearchResponse(
        jobs=jobs,
        total=total,
        page=page,
        per_page=per_page,
        has_more=(page * per_page) < total,
    )


@router.get("/search", response_model=JobSearchResponse)
async def search_jobs_endpoint(
    q: Optional[str] = Query(None, description="Search keyword"),
    location: Optional[str] = Query(None, description="Location filter"),
    type: Optional[str] = Query(None, alias="type", description="Job type filter"),
    source: Optional[str] = Query(None, description="Source filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Alternative search endpoint with 'type' alias."""
    jobs, total = search_jobs(
        q=q,
        location=location,
        job_type=type,
        source=source,
        page=page,
        per_page=per_page,
    )
    return JobSearchResponse(
        jobs=jobs,
        total=total,
        page=page,
        per_page=per_page,
        has_more=(page * per_page) < total,
    )


@router.get("/stats")
async def job_stats():
    """Return quick stats about the cached jobs."""
    all_jobs = get_all_jobs()
    sources: dict[str, int] = {}
    remote_count = 0
    for j in all_jobs:
        sources[j.source] = sources.get(j.source, 0) + 1
        if j.job_type == "remote" or "remote" in j.location.lower():
            remote_count += 1
    return {
        "total_jobs": len(all_jobs),
        "by_source": sources,
        "remote_jobs": remote_count,
    }


@router.get("/matched")
async def matched_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """
    Return jobs ranked by match score to the current user's profile/resume.
    Requires authentication.
    """
    supabase = get_supabase()

    # Get user profile
    try:
        profile_result = (
            supabase.table("profiles").select("*").eq("user_id", user["id"]).execute()
        )
        profile = (
            _decode_supabase_json_columns(profile_result.data[0])
            if profile_result.data
            else {}
        )

        resume_result = (
            supabase.table("resumes")
            .select("*")
            .eq("user_id", user["id"])
            .order("parsed_at", desc=True)
            .limit(1)
            .execute()
        )
        resume = (
            _decode_supabase_json_columns(resume_result.data[0])
            if resume_result.data
            else None
        )
    except Exception as e:
        logger.exception("Supabase error loading profile/resume for matched jobs")
        raise HTTPException(
            status_code=500,
            detail="Could not load profile data",
        ) from e

    if not profile.get("skills") and not resume:
        raise HTTPException(
            status_code=400,
            detail="Upload a resume or add skills to your profile first",
        )

    # Get all jobs and rank them
    all_jobs_list = get_all_jobs()
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
            _matched_job_payload(item["job"], item["match_score"])
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
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
