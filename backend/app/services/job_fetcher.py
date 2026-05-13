"""
Job Fetcher Service
-------------------
Fetches jobs from 5 sources, normalizes them, deduplicates, and caches.

Sources:
  1. Adzuna API (international, needs key)
  2. RemoteOK API (remote jobs, no key needed)
  3. Remotive API (remote jobs, no key needed)
  4. JobSpy / Indeed+Glassdoor (Pakistan local jobs, no key needed)
  5. JSearch / RapidAPI (Pakistan jobs, free 200 req/mo)
"""

import httpx
import asyncio
import logging
import re
import math
from typing import List, Optional
from app.config import settings
from app.models.schemas import Job

logger = logging.getLogger(__name__)


def _clean_description(html: str) -> str:
    """
    Clean job description HTML:
    - Remove empty/whitespace-only <p> tags (e.g. <p>&nbsp;</p>, <p> </p>)
    - Collapse 3+ consecutive <br> into 2
    - Trim excessive leading/trailing whitespace inside tags
    """
    if not html:
        return html
    # Remove empty paragraphs (with only whitespace or &nbsp;)
    html = re.sub(r'<p\b[^>]*>\s*(&nbsp;|\s)*\s*</p>', '', html, flags=re.IGNORECASE)
    # Collapse 3+ consecutive <br> tags into a single one
    html = re.sub(r'(<br\s*/?>[\s]*){3,}', '<br/><br/>', html, flags=re.IGNORECASE)
    # Remove empty <li> items
    html = re.sub(r'<li\b[^>]*>\s*(&nbsp;|\s)*\s*</li>', '', html, flags=re.IGNORECASE)
    return html.strip()

# ---------------------------------------------------------------------------
# In-memory job store (dict keyed by job id)
# ---------------------------------------------------------------------------
_job_store: dict[str, Job] = {}

KNOWN_TAGS = [
    "Python", "Machine Learning", "Data Science", "AI", "Deep Learning",
    "TensorFlow", "PyTorch", "Scikit-learn", "NLP", "Computer Vision",
    "SQL", "Pandas", "NumPy", "FastAPI", "Django", "Flask",
    "Docker", "AWS", "GCP", "Azure", "React", "Node.js",
    "JavaScript", "TypeScript", "Spark", "Airflow", "Power BI",
    "Tableau", "R", "HuggingFace", "LLM", "GPT", "Transformer",
    "Statistics", "MLOps", "ETL", "Data Engineering", "Streamlit",
    "Kubernetes", "Java", "Go", "Rust", "C++",
]


def _extract_tags(text: str) -> List[str]:
    """Extract relevant technology tags from text."""
    text_lower = text.lower()
    return [tag for tag in KNOWN_TAGS if tag.lower() in text_lower][:10]


def _format_salary(min_val, max_val, currency: str = "$") -> Optional[str]:
    """Format a min/max salary range into a readable string."""
    try:
        if min_val and max_val:
            return f"{currency}{int(float(min_val)):,} - {currency}{int(float(max_val)):,}"
        elif min_val:
            return f"{currency}{int(float(min_val)):,}+"
        elif max_val:
            return f"Up to {currency}{int(float(max_val)):,}"
    except (ValueError, TypeError):
        pass
    return None


# ===========================================================================
# ADZUNA CLIENT
# ===========================================================================
async def fetch_adzuna_jobs(
    query: str = "data science",
    country: str = "gb",
    page: int = 1,
    results_per_page: int = 50,
) -> List[Job]:
    """Fetch jobs from Adzuna API. Requires ADZUNA_APP_ID and ADZUNA_APP_KEY."""
    if not settings.ADZUNA_APP_ID or not settings.ADZUNA_APP_KEY:
        logger.warning("Adzuna API credentials not configured - skipping")
        return []

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
    params = {
        "app_id": settings.ADZUNA_APP_ID,
        "app_key": settings.ADZUNA_APP_KEY,
        "what": query,
        "results_per_page": results_per_page,
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        jobs: List[Job] = []
        for item in data.get("results", []):
            combined_text = f"{item.get('title', '')} {item.get('description', '')}"
            location = item.get("location", {}).get("display_name", "")
            jobs.append(
                Job(
                    id=f"adzuna_{item.get('id', '')}",
                    title=item.get("title", "").strip(),
                    company=item.get("company", {}).get("display_name", "Unknown"),
                    location=location,
                    salary=_format_salary(
                        item.get("salary_min"), item.get("salary_max")
                    ),
                    description=_clean_description(item.get("description", ""))[:10000],
                    url=item.get("redirect_url", ""),
                    source="adzuna",
                    posted_date=item.get("created", ""),
                    tags=_extract_tags(combined_text),
                    job_type=(
                        "remote"
                        if "remote" in combined_text.lower()
                        else "onsite"
                    ),
                )
            )
        logger.info(f"Adzuna ({country}/{query}): fetched {len(jobs)} jobs")
        return jobs

    except httpx.HTTPStatusError as e:
        logger.error(f"Adzuna API HTTP error ({country}): {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Adzuna API error ({country}): {e}")
        return []


# ===========================================================================
# REMOTEOK CLIENT
# ===========================================================================
async def fetch_remoteok_jobs() -> List[Job]:
    """Fetch jobs from RemoteOK public API (no auth required)."""
    url = "https://remoteok.com/api"
    headers = {"User-Agent": "JobFinderApp/1.0 (personal project)"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        relevant_keywords = {
            "python", "data", "machine learning", "ml", "ai",
            "data science", "fastapi", "scikit", "analytics",
            "deep learning", "nlp", "tensorflow", "pytorch",
        }

        jobs: List[Job] = []
        for item in data[1:]:  # first element is metadata
            if not isinstance(item, dict) or not item.get("position"):
                continue

            tags = item.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]

            title_lower = item.get("position", "").lower()
            tag_set = {t.lower() for t in tags}
            desc_lower = item.get("description", "")[:500].lower()
            combined = f"{title_lower} {' '.join(tag_set)} {desc_lower}"

            if not any(kw in combined for kw in relevant_keywords):
                continue

            slug = item.get("slug", item.get("id", ""))
            apply_url = item.get("url", "") or f"https://remoteok.com/remote-jobs/{slug}"

            jobs.append(
                Job(
                    id=f"remoteok_{item.get('id', '')}",
                    title=item.get("position", "").strip(),
                    company=item.get("company", "Unknown").strip(),
                    location=item.get("location", "Remote") or "Remote",
                    salary=_format_salary(
                        item.get("salary_min"), item.get("salary_max")
                    ),
                    description=_clean_description(item.get("description", ""))[:10000],
                    url=apply_url,
                    source="remoteok",
                    posted_date=item.get("date", ""),
                    tags=(tags[:10] if tags else _extract_tags(combined)),
                    job_type="remote",
                )
            )
        logger.info(f"RemoteOK: fetched {len(jobs)} relevant jobs")
        return jobs

    except Exception as e:
        logger.error(f"RemoteOK API error: {e}")
        return []


# ===========================================================================
# REMOTIVE CLIENT
# ===========================================================================
async def fetch_remotive_jobs(
    category: str = "software-dev",
    search: str = "",
    limit: int = 100,
) -> List[Job]:
    """Fetch jobs from Remotive public API (no auth required)."""
    url = "https://remotive.com/api/remote-jobs"
    params = {"category": category, "limit": limit}
    if search:
        params["search"] = search

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        jobs: List[Job] = []
        for item in data.get("jobs", []):
            tags = item.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]

            salary = item.get("salary", "")
            if not salary or salary.strip() == "":
                salary = None

            desc = _clean_description(item.get("description", ""))[:10000]

            jobs.append(
                Job(
                    id=f"remotive_{item.get('id', '')}",
                    title=item.get("title", "").strip(),
                    company=item.get("company_name", "Unknown").strip(),
                    location=item.get("candidate_required_location", "Remote") or "Remote",
                    salary=salary,
                    description=desc,
                    url=item.get("url", ""),
                    source="remotive",
                    posted_date=item.get("publication_date", ""),
                    tags=(tags[:10] if tags else _extract_tags(desc)),
                    job_type="remote",
                )
            )
        logger.info(f"Remotive ({category}/{search}): fetched {len(jobs)} jobs")
        return jobs

    except Exception as e:
        logger.error(f"Remotive API error: {e}")
        return []


# ===========================================================================
# JOBSPY CLIENT - Indeed + Google Jobs for Pakistan cities (NO API KEY NEEDED)
# ===========================================================================
async def fetch_jobspy_pakistan_jobs() -> List[Job]:
    """
    Use python-jobspy to scrape Indeed and Google Jobs for Pakistan cities.
    Runs in a thread pool since jobspy is synchronous.
    No API key required - this is the PRIMARY source for Pakistan jobs.
    """
    try:
        from jobspy import scrape_jobs as jobspy_scrape
    except ImportError:
        logger.warning("python-jobspy not installed - pip install python-jobspy")
        return []

    pakistan_searches = [
        {"term": "data science", "location": "Karachi", "country": "Pakistan"},
        {"term": "python developer", "location": "Karachi", "country": "Pakistan"},
        {"term": "machine learning", "location": "Karachi", "country": "Pakistan"},
        {"term": "software engineer", "location": "Karachi", "country": "Pakistan"},
        {"term": "data analyst", "location": "Karachi", "country": "Pakistan"},
        {"term": "AI engineer", "location": "Karachi", "country": "Pakistan"},
        {"term": "data science", "location": "Lahore", "country": "Pakistan"},
        {"term": "python developer", "location": "Lahore", "country": "Pakistan"},
        {"term": "software engineer", "location": "Lahore", "country": "Pakistan"},
        {"term": "data science", "location": "Islamabad", "country": "Pakistan"},
        {"term": "python developer", "location": "Islamabad", "country": "Pakistan"},
        {"term": "software engineer", "location": "Islamabad", "country": "Pakistan"},
    ]

    def _scrape_one(search: dict) -> List[Job]:
        try:
            df = jobspy_scrape(
                site_name=["indeed", "google"],
                search_term=search["term"],
                location=search["location"],
                results_wanted=15,
                country_indeed=search["country"],
            )
            jobs_list: List[Job] = []
            for _, row in df.iterrows():
                title = str(row.get("title", "")).strip()
                if not title or title == "nan":
                    continue

                company = str(row.get("company_name", row.get("company", "Unknown"))).strip()
                if company == "nan":
                    company = "Unknown"

                loc = str(row.get("location", "")).strip()
                if not loc or loc == "nan":
                    loc = f"{search['location']}, Pakistan"
                elif "pakistan" not in loc.lower():
                    loc = f"{loc}, Pakistan"

                # Salary
                salary = None
                sal_min = row.get("min_amount", None)
                sal_max = row.get("max_amount", None)
                if sal_min is not None and not (isinstance(sal_min, float) and math.isnan(sal_min)):
                    currency = str(row.get("currency", "PKR"))
                    if currency == "nan":
                        currency = "PKR"
                    salary = _format_salary(sal_min, sal_max, f"{currency} ")

                # Description
                desc = str(row.get("description", ""))[:2000]
                if desc == "nan":
                    desc = ""

                # URL
                url = str(row.get("job_url", row.get("link", "")))
                if url == "nan":
                    url = ""

                # Posted date
                posted = row.get("date_posted", None)
                posted_str = ""
                if posted and str(posted) != "nan" and str(posted) != "NaT":
                    try:
                        posted_str = str(posted)[:10]
                    except Exception:
                        pass

                site = str(row.get("site", "indeed")).lower()
                source_name = "indeed" if "indeed" in site else "google"

                job_id = f"{source_name}_{abs(hash(f'{title}{company}{loc}'))}"
                combined = f"{title} {desc}"

                jobs_list.append(
                    Job(
                        id=job_id,
                        title=title,
                        company=company,
                        location=loc,
                        salary=salary,
                        description=desc,
                        url=url,
                        source=source_name,
                        posted_date=posted_str,
                        tags=_extract_tags(combined),
                        job_type="remote" if "remote" in combined.lower() else "onsite",
                    )
                )
            return jobs_list
        except Exception as e:
            logger.error(f"JobSpy scrape error ({search['term']} in {search['location']}): {e}")
            return []

    # Run searches in thread pool (jobspy is synchronous)
    loop = asyncio.get_event_loop()
    all_jobs: List[Job] = []

    for search in pakistan_searches:
        try:
            jobs = await loop.run_in_executor(None, _scrape_one, search)
            all_jobs.extend(jobs)
            logger.info(f"JobSpy ({search['term']} in {search['location']}): {len(jobs)} jobs")
            # Small delay between scrapes to be respectful
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"JobSpy executor error: {e}")

    logger.info(f"JobSpy Pakistan total: {len(all_jobs)} jobs")
    return all_jobs


# ===========================================================================
# JSEARCH CLIENT - RapidAPI (free 200 req/month)
# ===========================================================================
async def fetch_jsearch_jobs(
    query: str = "data science in Pakistan",
    page: int = 1,
) -> List[Job]:
    """
    Fetch jobs from JSearch API on RapidAPI.
    Free tier: 200 requests/month. Set JSEARCH_API_KEY in .env.
    """
    if not settings.JSEARCH_API_KEY:
        logger.warning("JSearch API key not configured - skipping")
        return []

    url = "https://jsearch.p.rapidapi.com/search"
    params = {
        "query": query,
        "page": str(page),
        "num_pages": "1",
        "country": "pk",
    }
    headers = {
        "x-rapidapi-key": settings.JSEARCH_API_KEY,
        "x-rapidapi-host": "jsearch.p.rapidapi.com",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

        jobs: List[Job] = []
        for item in data.get("data", []):
            title = item.get("job_title", "").strip()
            company = item.get("employer_name", "Unknown").strip()
            city = item.get("job_city", "")
            state = item.get("job_state", "")
            country = item.get("job_country", "Pakistan")
            loc_parts = [p for p in [city, state, country] if p]
            location = ", ".join(loc_parts) or "Pakistan"

            desc = item.get("job_description", "")[:2000]
            apply_url = item.get("job_apply_link", "")
            posted = item.get("job_posted_at_datetime_utc", "")

            sal_min = item.get("job_min_salary")
            sal_max = item.get("job_max_salary")
            currency = item.get("job_salary_currency", "PKR")
            salary = _format_salary(sal_min, sal_max, f"{currency} ") if sal_min or sal_max else None

            is_remote = item.get("job_is_remote", False)

            jobs.append(
                Job(
                    id=f"jsearch_{item.get('job_id', abs(hash(f'{title}{company}')))}",
                    title=title,
                    company=company,
                    location=location,
                    salary=salary,
                    description=desc,
                    url=apply_url,
                    source="jsearch",
                    posted_date=posted[:10] if posted else "",
                    tags=_extract_tags(f"{title} {desc}"),
                    job_type="remote" if is_remote else "onsite",
                )
            )
        logger.info(f"JSearch ({query}): fetched {len(jobs)} jobs")
        return jobs

    except Exception as e:
        logger.error(f"JSearch API error: {e}")
        return []


# ===========================================================================
# AGGREGATOR - fetch all, deduplicate, cache
# ===========================================================================
async def fetch_all_jobs() -> List[Job]:
    """Fetch jobs from ALL sources, deduplicate, and cache."""
    logger.info("=== Starting full job fetch from all sources ===")

    # ---- Phase 1: API sources (fast, concurrent) ----
    api_tasks = [
        # RemoteOK (remote tech/data jobs)
        fetch_remoteok_jobs(),
        # Remotive (remote jobs, two categories)
        fetch_remotive_jobs(category="software-dev", search="python"),
        fetch_remotive_jobs(category="data"),
        # Adzuna (international)
        fetch_adzuna_jobs(query="data science python remote", country="gb"),
        fetch_adzuna_jobs(query="machine learning AI remote", country="us"),
        fetch_adzuna_jobs(query="data science python", country="in"),
        fetch_adzuna_jobs(query="data science python", country="pk"),
        fetch_adzuna_jobs(query="software developer python", country="pk"),
        # JSearch (Pakistan-specific via RapidAPI)
        fetch_jsearch_jobs(query="data science in Karachi Pakistan"),
        fetch_jsearch_jobs(query="python developer in Pakistan"),
        fetch_jsearch_jobs(query="machine learning in Lahore Pakistan"),
        fetch_jsearch_jobs(query="software engineer in Islamabad Pakistan"),
    ]

    api_results = await asyncio.gather(*api_tasks, return_exceptions=True)

    all_jobs: List[Job] = []
    for result in api_results:
        if isinstance(result, Exception):
            logger.error(f"API fetch task failed: {result}")
        elif isinstance(result, list):
            all_jobs.extend(result)

    # ---- Phase 2: JobSpy scraping for Pakistan cities (slower) ----
    try:
        pakistan_jobs = await fetch_jobspy_pakistan_jobs()
        all_jobs.extend(pakistan_jobs)
    except Exception as e:
        logger.error(f"JobSpy Pakistan fetch failed: {e}")

    # Deduplicate by normalized title + company
    seen: set[str] = set()
    unique_jobs: List[Job] = []
    for job in all_jobs:
        key = f"{job.title.lower().strip()}|{job.company.lower().strip()}"
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)

    # Update in-memory store
    global _job_store
    _job_store = {job.id: job for job in unique_jobs}

    logger.info(f"=== Total: {len(unique_jobs)} unique jobs cached ===")
    return unique_jobs


# ===========================================================================
# STORE ACCESS
# ===========================================================================
def get_all_jobs() -> List[Job]:
    """Return all cached jobs."""
    return list(_job_store.values())


def get_job_by_id(job_id: str) -> Optional[Job]:
    """Return a single job by ID."""
    return _job_store.get(job_id)


def search_jobs(
    q: Optional[str] = None,
    location: Optional[str] = None,
    job_type: Optional[str] = None,
    source: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[List[Job], int]:
    """Search and filter the in-memory job cache. Returns (paginated_jobs, total)."""
    jobs = list(_job_store.values())

    # Text search across title, description, company, tags
    if q:
        q_lower = q.lower()
        jobs = [
            j
            for j in jobs
            if q_lower in j.title.lower()
            or q_lower in j.description.lower()
            or q_lower in j.company.lower()
            or any(q_lower in t.lower() for t in j.tags)
        ]

    # Location filter
    if location:
        loc = location.lower()
        if loc == "remote":
            jobs = [
                j
                for j in jobs
                if j.job_type == "remote" or "remote" in j.location.lower()
            ]
        else:
            jobs = [j for j in jobs if loc in j.location.lower()]

    # Job type filter
    if job_type:
        jt = job_type.lower().replace("-", "").replace("_", "")
        if jt == "remote":
            jobs = [
                j
                for j in jobs
                if j.job_type == "remote" or "remote" in j.location.lower()
            ]
        elif jt in ("fulltime", "full time"):
            jobs = [
                j
                for j in jobs
                if "full" in (j.title + " " + j.description[:300]).lower()
            ]
        elif jt in ("parttime", "part time"):
            jobs = [
                j
                for j in jobs
                if "part" in (j.title + " " + j.description[:300]).lower()
            ]
        elif jt == "internship":
            jobs = [j for j in jobs if "intern" in j.title.lower()]

    # Source filter
    if source:
        jobs = [j for j in jobs if j.source == source.lower()]

    # Sort by posted_date (newest first)
    jobs.sort(key=lambda j: j.posted_date or "", reverse=True)

    total = len(jobs)
    start = (page - 1) * per_page
    paginated = jobs[start : start + per_page]

    return paginated, total
