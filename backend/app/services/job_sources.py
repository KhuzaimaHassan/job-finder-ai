"""Bounded provider adapters. Failures remain visible to the ingestion coordinator."""
import asyncio
import hashlib
import logging
import random
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.schemas.jobs import Job
from app.services.job_policy import parse_date, relevant_role

logger = logging.getLogger(__name__)


class Feed(list):
    def __init__(self, jobs=(), *, capped=False, error=None):
        super().__init__(jobs)
        self.capped, self.error = capped, error


async def request_json(client, url, params=None, headers=None, attempts=3):
    for attempt in range(attempts):
        try:
            response = await client.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and data.get("success") is False:
                raise ValueError("Provider returned an unsuccessful response")
            return data
        except httpx.HTTPStatusError as exc:
            # Respect rate limits by ending this pass; coordinator applies cooldown.
            if exc.response.status_code < 500 or attempt == attempts - 1:
                raise
        except httpx.TransportError:
            if attempt == attempts - 1:
                raise
        await asyncio.sleep(2 ** attempt + random.random())


def date_string(value):
    date = parse_date(value)
    return date.isoformat() if date else None


def salary(low, high, currency="USD"):
    try:
        values = [f"{float(value):,.0f}" for value in (low, high) if value]
        return f"{currency} " + " - ".join(values) if values else None
    except (TypeError, ValueError):
        return None


def tags(text):
    from app.services.job_fetcher import _extract_tags
    return _extract_tags(text)


def add_record(result, parser, item):
    try:
        job = parser(item)
        if relevant_role(job):
            result.append(job)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError):
        logger.debug("Skipped malformed or expired provider record")


def _parse_himalayas_job(item):
    if (expiry := parse_date(item.get("expiryDate"))) and expiry <= datetime.now(timezone.utc):
        raise ValueError("Expired listing")
    title = (item.get("title") or "").strip()
    if not title:
        raise ValueError("Missing title")
    company = item.get("companyName") or "Unknown"
    url = item.get("applicationLink") or item.get("url") or ""
    identity = item.get("guid") or item.get("id") or url or f"{title}|{company}"
    desc = item.get("description") or item.get("excerpt") or ""
    pay = salary(item.get("minSalary"), item.get("maxSalary"), item.get("currency") or "USD")
    if pay and item.get("salaryPeriod"):
        pay += f" / {item['salaryPeriod']}"
    return Job(id="himalayas_" + hashlib.sha256(str(identity).encode()).hexdigest()[:24],
               title=title, company=company, location=", ".join((item.get("locationRestrictions") or [])[:5]) or "Remote",
               description=desc[:10000], url=url, source="himalayas", provider_id=str(identity),
               source_url=str(identity) if str(identity).startswith("https://himalayas.app/") else "https://himalayas.app",
               posted_date=date_string(item.get("pubDate") or item.get("publication_date")),
               expires_at=date_string(item.get("expiryDate")),
               location_restrictions=item.get("locationRestrictions") or [],
               timezone_restrictions=[round(float(value) * 60) for value in item.get("timezoneRestrictions", [])],
               employment_type=item.get("employmentType"), job_type="remote", availability="active",
               tags=tags(f"{title} {desc}"), salary=pay)


async def fetch_himalayas_jobs(search="python", limit=None):
    result, seen = [], set()
    maximum = limit or settings.JOB_PROVIDER_MAX_PAGES * 20
    async with httpx.AsyncClient() as client:
        for page in range(1, settings.JOB_PROVIDER_MAX_PAGES + 1):
            try:
                data = await request_json(client, "https://himalayas.app/jobs/api/search", {"q": search, "sort": "recent", "page": page})
                items = data.get("jobs", [])
                if not items:
                    return Feed(result)
                fresh = []
                for item in items:
                    add_record(fresh, _parse_himalayas_job, item)
                added = [job for job in fresh if job.id not in seen]
                result.extend(added)
                seen.update(job.id for job in added)
                if not added and fresh:
                    return Feed(result)
                if len(result) >= maximum:
                    return Feed(result[:maximum], capped=True)
                await asyncio.sleep(1.1)
            except Exception as exc:
                if not result:
                    raise
                return Feed(result, error=type(exc).__name__)
    return Feed(result, capped=True)


def parse_jobicy(item):
    identity = str(item["id"])
    title = item["jobTitle"].strip()
    desc = item.get("jobDescription") or item.get("jobExcerpt") or ""
    kind = item.get("jobType") or []
    url = item.get("url") or ""
    return Job(id=f"jobicy_{identity}", provider_id=identity, source_url=url, source="jobicy",
               title=title, company=item.get("companyName") or "Unknown", location=item.get("jobGeo") or "Remote",
               description=desc[:10000], url=url, posted_date=date_string(item.get("pubDate")),
               employment_type=" ".join(kind) if isinstance(kind, list) else kind,
               job_type="remote", availability="active", tags=tags(f"{title} {desc}"),
               salary=salary(item.get("salaryMin"), item.get("salaryMax"), item.get("salaryCurrency") or "USD"))


async def fetch_jobicy_jobs(count=100, tag=""):
    result, cursor, cursors = [], None, set()
    async with httpx.AsyncClient() as client:
        for _ in range(settings.JOB_PROVIDER_MAX_PAGES):
            params = {"count": count}
            if tag:
                params["tag"] = tag
            if cursor:
                params["cursor"] = cursor
            try:
                data = await request_json(client, "https://jobicy.com/api/jobs", params)
                for item in data.get("jobs", []):
                    add_record(result, parse_jobicy, item)
                cursor = data.get("nextCursor")
                if not cursor or cursor in cursors:
                    return Feed(result)
                cursors.add(cursor)
                await asyncio.sleep(1.1)
            except Exception as exc:
                if not result:
                    raise
                return Feed(result, error=type(exc).__name__)
    return Feed(result, capped=True)


async def jobicy_status(ids):
    result = {}
    async with httpx.AsyncClient() as client:
        for offset in range(0, len(ids), 100):
            data = await request_json(client, "https://jobicy.com/api/jobs/status", {"ids": ",".join(ids[offset:offset + 100])})
            for item in data.get("jobs", []):
                if item.get("status") in ("active", "closed", "unknown"):
                    result[f"jobicy_{item['id']}"] = item["status"]
            await asyncio.sleep(1.1)
    return result


async def fetch_remotive_jobs(category="", search="", limit=None):
    # One broad feed per six-hour pass; filter locally instead of 15 requests.
    params = {}
    if category:
        params["category"] = category
    if search:
        params["search"] = search
    if limit:
        params["limit"] = limit
    async with httpx.AsyncClient() as client:
        data = await request_json(client, "https://remotive.com/api/remote-jobs", params, attempts=1)
    def parse(item):
        title, desc = item["title"], item.get("description") or ""
        return Job(id=f"remotive_{item['id']}", provider_id=str(item["id"]), title=title,
                   company=item.get("company_name") or "Unknown", location=item.get("candidate_required_location") or "Remote",
                   description=desc[:10000], url=item.get("url") or "", source_url=item.get("url"), source="remotive",
                   salary=item.get("salary") or None, posted_date=date_string(item.get("publication_date")),
                   employment_type=item.get("job_type"), job_type="remote", availability="active", tags=tags(f"{title} {desc}"))
    result = []
    for item in data.get("jobs", []):
        add_record(result, parse, item)
    return Feed(result)


async def fetch_remoteok_jobs():
    async with httpx.AsyncClient() as client:
        data = await request_json(client, "https://remoteok.com/api", headers={"User-Agent": "JobFinderApp/1.0"})
    def parse(item):
        title, desc = item["position"], item.get("description") or ""
        return Job(id=f"remoteok_{item['id']}", provider_id=str(item["id"]), title=title,
                   company=item.get("company") or "Unknown", location=item.get("location") or "Remote",
                   description=desc[:10000], url=item.get("url") or "", source_url=item.get("url"), source="remoteok",
                   posted_date=date_string(item.get("date")), job_type="remote", availability="active", tags=tags(f"{title} {desc}"),
                   salary=salary(item.get("salary_min"), item.get("salary_max")))
    result = []
    for item in data:
        add_record(result, parse, item)
    return Feed(result)


async def fetch_adzuna_jobs(query="data science python remote", country="gb", page=1, results_per_page=50):
    if not settings.ADZUNA_APP_ID or not settings.ADZUNA_APP_KEY:
        return Feed()
    result = []
    async with httpx.AsyncClient() as client:
        for number in range(page, page + settings.JOB_PROVIDER_MAX_PAGES):
            try:
                data = await request_json(client, f"https://api.adzuna.com/v1/api/jobs/{country}/search/{number}",
                    {"app_id": settings.ADZUNA_APP_ID, "app_key": settings.ADZUNA_APP_KEY, "what": query,
                     "results_per_page": results_per_page, "max_days_old": settings.JOB_POSTED_MAX_AGE_DAYS, "sort_by": "date"})
                items = data.get("results", [])
                def parse(item):
                    title, desc = item["title"], item.get("description") or ""
                    return Job(id=f"adzuna_{item['id']}", provider_id=str(item["id"]), title=title,
                        company=(item.get("company") or {}).get("display_name") or "Unknown",
                        location=(item.get("location") or {}).get("display_name") or "", description=desc[:10000],
                        url=item.get("redirect_url") or "", source="adzuna", posted_date=date_string(item.get("created")),
                        job_type="remote" if "remote" in f"{title} {desc}".lower() else "onsite", availability="active",
                        location_restrictions=[country],
                        employment_type=item.get("contract_time"), tags=tags(f"{title} {desc}"), salary=salary(item.get("salary_min"), item.get("salary_max")))
                for item in items:
                    add_record(result, parse, item)
                if len(items) < results_per_page:
                    return Feed(result)
                await asyncio.sleep(1.1)
            except Exception as exc:
                if not result:
                    raise
                return Feed(result, error=type(exc).__name__)
    return Feed(result, capped=True)
