"""Read-only freshness audit. Run from backend; never triggers an ingestion run."""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parse_date(value):
    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
    except (ValueError, TypeError):
        return None


def summarize(rows, now):
    dates = [date for row in rows if (date := parse_date(row.get("posted_date")))]
    ages = [(now - date).total_seconds() / 86400 for date in dates]
    return {
        "count": len(rows),
        "parseable_dates": len(dates),
        "within_1_day": sum(0 <= age < 1 for age in ages),
        "within_7_days": sum(0 <= age <= 7 for age in ages),
        "older_than_14_days": sum(age > 14 for age in ages),
        "older_than_30_days": sum(age > 30 for age in ages),
        "future_dates": sum(age < 0 for age in ages),
        "oldest_date": min(dates).isoformat() if dates else None,
        "newest_date": max(dates).isoformat() if dates else None,
    }


def read_json(client, url, params=None):
    # One retry accommodates a cold web-service startup; this calls our API only.
    for attempt in range(2):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.TransportError, httpx.HTTPStatusError):
            if attempt:
                raise


def audit(base_url, include_database):
    now = datetime.now(timezone.utc)
    report = {"checked_at_utc": now.isoformat(), "api_url": base_url}
    active = None
    with httpx.Client(timeout=45) as client:
        try:
            report["health"] = read_json(client, base_url + "/api/health")
            first = read_json(client, base_url + "/api/jobs", {"per_page": 100})
            active = list(first["jobs"])
            for page in range(2, math.ceil(first["total"] / 100) + 1):
                active.extend(read_json(client, base_url + "/api/jobs", {"per_page": 100, "page": page})["jobs"])
            report["search"] = summarize(active, now)
            report["search"]["reported_total"] = first["total"]
            report["sources"] = {
                source: summarize([row for row in active if row["source"] == source], now)
                for source in sorted({row["source"] for row in active})
            }
        except Exception as exc:
            report["public_read_error"] = type(exc).__name__

    if include_database:
        try:
            from app.config import settings
            from supabase import create_client

            # Only the public jobs table is read; no service-role access is needed.
            db = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            rows = []
            for offset in range(0, 50000, 1000):
                batch = db.table("jobs").select("id,source,posted_date,fetched_at").order("id").range(offset, offset + 999).execute().data
                rows.extend(batch)
                if len(batch) < 1000:
                    break
            cutoff = now - timedelta(days=settings.JOB_CACHE_MAX_AGE_DAYS)
            stale_ids = {row["id"] for row in rows if (date := parse_date(row.get("fetched_at"))) and date < cutoff}
            observed = defaultdict(list)
            for row in rows:
                if date := parse_date(row.get("fetched_at")):
                    observed[row["source"]].append(date)
            report["database"] = {
                "rows_read": len(rows),
                "scan_limit_reached": len(rows) == 50000,
                "last_seen_cutoff_utc": cutoff.isoformat(),
                "older_than_cutoff": len(stale_ids),
                "stale_ids_in_search": sum(row["id"] in stale_ids for row in active) if active is not None else None,
                "newest_fetched_at_by_source": {source: max(dates).isoformat() for source, dates in sorted(observed.items())},
            }
        except Exception as exc:
            report["database_read_error"] = type(exc).__name__
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="https://job-finder-ai-backend.onrender.com")
    parser.add_argument("--database", action="store_true", help="Also read the public jobs table configured in backend/.env")
    parser.add_argument("--output", type=Path, help="Optional local JSON report path")
    args = parser.parse_args()
    result = audit(args.api_url.rstrip("/"), args.database)
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)
    sys.exit(1 if "public_read_error" in result or "database_read_error" in result else 0)
