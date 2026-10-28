from pydantic import BaseModel, model_validator
from typing import Optional, List
from app.services.job_normalization import employment_type, work_arrangement


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
    is_active: bool = True
    employment_type: Optional[str] = None
    fetched_at: Optional[str] = None
    first_seen_at: Optional[str] = None
    expires_at: Optional[str] = None
    availability: str = "unverified"
    provider_id: Optional[str] = None
    source_url: Optional[str] = None
    location_restrictions: List[str] = []
    timezone_restrictions: List[int] = []  # minutes east of UTC, including half-hour offsets

    @model_validator(mode="after")
    def normalize_classification(self):
        text = f"{self.title} {self.description}"
        self.employment_type = employment_type(self.employment_type or "") or employment_type(text)
        self.job_type = work_arrangement(text, self.job_type)
        return self


class JobSearchResponse(BaseModel):
    """Paginated response for job search."""
    jobs: List[Job]
    total: int
    page: int
    per_page: int
    has_more: bool
