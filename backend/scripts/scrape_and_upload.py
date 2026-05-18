#!/usr/bin/env python3
"""
scrape_and_upload.py
--------------------
Local scraper that fetches Pakistan + remote jobs using JobSpy (works on
residential IPs) and upserts them into Supabase for the production backend.

Usage:
    cd backend
    python scripts/scrape_and_upload.py

Run this manually whenever you want to refresh job listings.
Jobs persist in Supabase so the production backend always has them.

Notes:
  - Glassdoor does NOT support Pakistan — Indeed only is used for PK cities.
  - LinkedIn is used for remote searches (global, no country restriction).
"""

import sys
import os
import logging
import hashlib
import re
from datetime import datetime, timedelta

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # service role for writes

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    logger.error("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in backend/.env")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ---------------------------------------------------------------------------
# Scraping configuration
# ---------------------------------------------------------------------------
SEARCHES = [
    # Pakistan cities — Indeed only (Glassdoor doesn't support PK)
    {"term": "data science",      "location": "Karachi, Pakistan",   "sites": ["indeed"]},
    {"term": "machine learning",  "location": "Karachi, Pakistan",   "sites": ["indeed"]},
    {"term": "python developer",  "location": "Karachi, Pakistan",   "sites": ["indeed"]},
    {"term": "software engineer", "location": "Karachi, Pakistan",   "sites": ["indeed"]},
    {"term": "data analyst",      "location": "Karachi, Pakistan",   "sites": ["indeed"]},
    {"term": "AI engineer",       "location": "Karachi, Pakistan",   "sites": ["indeed"]},
    {"term": "data science",      "location": "Lahore, Pakistan",    "sites": ["indeed"]},
    {"term": "python developer",  "location": "Lahore, Pakistan",    "sites": ["indeed"]},
    {"term": "software engineer", "location": "Lahore, Pakistan",    "sites": ["indeed"]},
    {"term": "machine learning",  "location": "Lahore, Pakistan",    "sites": ["indeed"]},
    {"term": "data science",      "location": "Islamabad, Pakistan", "sites": ["indeed"]},
    {"term": "software engineer", "location": "Islamabad, Pakistan", "sites": ["indeed"]},
    {"term": "python developer",  "location": "Islamabad, Pakistan", "sites": ["indeed"]},
    # Remote searches — LinkedIn (global, no country restriction needed)
    {"term": "data science remote",        "location": "", "sites": ["linkedin"]},
    {"term": "machine learning remote",    "location": "", "sites": ["linkedin"]},
    {"term": "python developer remote",    "location": "", "sites": ["linkedin"]},
    {"term": "AI engineer remote",         "location": "", "sites": ["linkedin"]},
]

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

PAKISTAN_LOCATIONS = {
    "pakistan", "karachi", "lahore", "islamabad", "rawalpindi", "peshawar",
    "faisalabad", "multan", "quetta", "sialkot", "gujranwala",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clean_html(html: str) -> str:
    """Strip HTML tags from description."""
    if not html:
        return ""
    return re.sub(r"<[^>]+>", " ", html).strip()[:5000]


def _extract_tags(text: str) -> list:
    text_lower = text.lower()
    return [tag for tag in KNOWN_TAGS if tag.lower() in text_lower][:10]


def _make_job_id(source: str, title: str, company: str) -> str:
    key = f"{source}_{title.lower().strip()}_{company.lower().strip()}"
    return f"{source}_{hashlib.md5(key.encode()).hexdigest()[:12]}"


def _detect_job_type(row) -> str:
    """Detect remote/onsite/hybrid from jobspy result."""
    is_remote = getattr(row, "is_remote", False)
    if is_remote:
        return "remote"
    job_type = str(getattr(row, "job_type", "") or "").lower()
    if "remote" in job_type:
        return "remote"
    if "hybrid" in job_type:
        return "hybrid"
    return "onsite"


def _is_relevant(location: str, job_type: str) -> bool:
    """Keep Pakistan onsite/hybrid + all remote jobs. Drop India/other onsite."""
    loc = location.lower()
    if job_type == "remote":
        return True
    if any(pk in loc for pk in PAKISTAN_LOCATIONS):
        return True
    exclusions = {
        "india", "mumbai", "delhi", "bangalore", "bengaluru", "chennai",
        "pune", "noida", "gurgaon", "kolkata",
        "brazil", "argentina", "nigeria", "south africa",
        "germany", "france", "japan", "china", "singapore",
    }
    if any(ex in loc for ex in exclusions):
        return False
    return True


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------
def scrape_jobs() -> list:
    """Run JobSpy searches and return normalized job dicts."""
    try:
        from jobspy import scrape_jobs as jobspy_scrape
    except ImportError:
        logger.error("jobspy not installed. Run: pip install python-jobspy")
        sys.exit(1)

    all_jobs = []
    seen_ids = set()

    for search in SEARCHES:
        term = search["term"]
        location = search["location"]
        sites = search["sites"]
        is_remote = not location

        logger.info(f"Scraping [{'/'.join(sites)}]: '{term}' in '{location or 'Remote/Global'}'...")

        try:
            kwargs = {
                "site_name": sites,
                "search_term": term,
                "results_wanted": 15 if is_remote else 20,
                "hours_old": 168,  # 7 days
            }
            if location:
                kwargs["location"] = location
                kwargs["country_indeed"] = "Pakistan"

            df = jobspy_scrape(**kwargs)

            if df is None or df.empty:
                logger.info("  → No results")
                continue

            count = 0
            for _, row in df.iterrows():
                title = str(getattr(row, "title", "") or "").strip()
                company = str(getattr(row, "company", "") or "Unknown").strip()
                if not title:
                    continue

                job_location = str(getattr(row, "location", "") or location or "Remote").strip()
                job_type = _detect_job_type(row)

                if not _is_relevant(job_location, job_type):
                    continue

                desc_raw = getattr(row, "description", "") or ""
                description = _clean_html(str(desc_raw))

                url = str(getattr(row, "job_url", "") or "").strip()
                if not url:
                    continue

                source = str(getattr(row, "site", sites[0])).lower()
                job_id = _make_job_id(source, title, company)

                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                # Date
                date_posted = getattr(row, "date_posted", None)
                posted_str = ""
                if date_posted:
                    try:
                        posted_str = str(date_posted)[:10]
                    except Exception:
                        pass

                # Salary
                salary = None
                min_sal = getattr(row, "min_amount", None)
                max_sal = getattr(row, "max_amount", None)
                currency = getattr(row, "currency", "") or ""
                if min_sal and max_sal:
                    salary = f"{currency}{int(min_sal):,}–{int(max_sal):,}"
                elif min_sal:
                    salary = f"{currency}{int(min_sal):,}+"

                tags = _extract_tags(f"{title} {description[:300]}")

                all_jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "location": job_location,
                    "salary": salary,
                    "description": description,
                    "url": url,
                    "source": source,
                    "posted_date": posted_str,
                    "tags": tags,
                    "job_type": job_type,
                    "fetched_at": datetime.utcnow().isoformat(),
                })
                count += 1

            logger.info(f"  → {count} relevant jobs")

        except Exception as e:
            logger.warning(f"  → Failed: {e}")

    return all_jobs


# ---------------------------------------------------------------------------
# Supabase upload
# ---------------------------------------------------------------------------
def upload_to_supabase(jobs: list) -> int:
    """Upsert jobs into Supabase. Returns count of upserted rows."""
    if not jobs:
        logger.info("No jobs to upload.")
        return 0

    batch_size = 100
    total_upserted = 0

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i:i + batch_size]
        try:
            supabase.table("jobs").upsert(batch, on_conflict="id").execute()
            total_upserted += len(batch)
            logger.info(f"  Upserted batch {i // batch_size + 1}: {len(batch)} jobs")
        except Exception as e:
            logger.error(f"  Batch upsert failed: {e}")

    return total_upserted


def delete_old_jobs(days: int = 14) -> None:
    """Remove jobs older than `days` days to keep the table clean."""
    try:
        cutoff_dt = (datetime.utcnow() - timedelta(days=days)).isoformat()
        supabase.table("jobs").delete().lt("fetched_at", cutoff_dt).execute()
        logger.info(f"Cleaned up jobs older than {days} days")
    except Exception as e:
        logger.warning(f"Cleanup failed (non-critical): {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    logger.info("=" * 55)
    logger.info("  Job Finder — Local Scraper & Supabase Uploader")
    logger.info("=" * 55)

    logger.info("\n📡 Scraping jobs locally (residential IP)...")
    jobs = scrape_jobs()
    logger.info(f"\n✅ Scraped {len(jobs)} relevant jobs total")

    if not jobs:
        logger.warning("No jobs scraped. Check connection or try again later.")
        return

    logger.info(f"\n⬆️  Uploading to Supabase...")
    upserted = upload_to_supabase(jobs)
    logger.info(f"✅ {upserted} jobs upserted to Supabase")

    logger.info(f"\n🧹 Cleaning up listings older than 14 days...")
    delete_old_jobs(days=14)

    try:
        result = supabase.table("jobs").select("id", count="exact").execute()
        logger.info(f"\n📊 Total jobs now in Supabase: {result.count}")
    except Exception:
        pass

    logger.info("\n🎉 Done! Trigger a Render redeploy to serve these jobs in production.")


if __name__ == "__main__":
    main()
