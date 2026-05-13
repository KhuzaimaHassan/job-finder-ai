from pydantic import BaseModel
from typing import Optional, List


class Job(BaseModel):
    """Unified job schema — normalized from all 3 API sources."""
    id: str
    title: str
    company: str
    location: str
    salary: Optional[str] = None
    description: str
    url: str
    source: str  # "adzuna" | "remoteok" | "remotive"
    posted_date: Optional[str] = None
    tags: List[str] = []
    job_type: Optional[str] = None  # "remote" | "onsite" | "hybrid"


class JobSearchResponse(BaseModel):
    """Paginated response for job search."""
    jobs: List[Job]
    total: int
    page: int
    per_page: int
    has_more: bool
