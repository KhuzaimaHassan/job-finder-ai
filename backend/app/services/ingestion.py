"""Durable provider budgets, cross-process leases, run history and safe publication."""
import asyncio
from datetime import datetime, timezone, timedelta
import logging
from uuid import uuid4
from email.utils import parsedate_to_datetime

import httpx

from app.config import settings
from app.services import job_fetcher as jf
from app.services.job_policy import parse_date, searchable
from app.services.job_sources import Feed, jobicy_status
from app.services.db_retry import db_call

logger = logging.getLogger(__name__)
_lock = asyncio.Lock()
_status = {"running": False, "sources": {}, "last_completed_at": None}


def status():
    return {**_status, "ready": jf.cache_ready(), "jobs_cached": len(jf.get_all_jobs()),
            "max_posted_age_days": settings.JOB_POSTED_MAX_AGE_DAYS,
            "max_unseen_age_days": settings.JOB_CACHE_MAX_AGE_DAYS}


def due(source, sources, now):
    next_due = parse_date(sources.get(source, {}).get("next_due_at"))
    return next_due is None or next_due <= now


async def _himalayas():
    jobs, errors, capped = [], [], False
    for query in ("python", "data science", "machine learning", "AI engineer", "software engineer"):
        try:
            feed = await jf.fetch_himalayas_jobs(query)
            jobs.extend(feed)
            capped |= getattr(feed, "capped", False)
            if getattr(feed, "error", None):
                errors.append(feed.error)
        except Exception as exc:
            errors.append(type(exc).__name__)
            break  # Especially 429: do not continue issuing queries.
    if errors and not jobs:
        raise RuntimeError(errors[0])
    return Feed(jobs, capped=capped, error=", ".join(errors) or None)


async def _adzuna():
    jobs, errors, capped = [], [], False
    for country in ("gb", "us", "in"):
        try:
            feed = await jf.fetch_adzuna_jobs(country=country)
            jobs.extend(feed)
            capped |= getattr(feed, "capped", False)
            if getattr(feed, "error", None):
                errors.append(feed.error)
        except Exception as exc:
            errors.append(type(exc).__name__)
            break
    if errors and not jobs:
        raise RuntimeError(errors[0])
    return Feed(jobs, capped=capped, error=", ".join(errors) or None)


async def _jobicy():
    feed = await jf.fetch_jobicy_jobs()
    # Reconcile stored IDs independently of feed pagination/publication window.
    ids = {job.provider_id or job.id.removeprefix("jobicy_") for job in jf._job_store.values()
           if job.source == "jobicy" and searchable(job)}
    # Fresh feed rows are already active; check missing cached IDs instead.
    ids.difference_update(job.provider_id for job in feed if job.provider_id)
    try:
        pending = sorted(value for value in ids if value and value.isdecimal())
        offset = _status.get("sources", {}).get("jobicy", {}).get("recheck_cursor", 0)
        offset = offset % len(pending) if pending else 0
        batch = (pending[offset:] + pending[:offset])[:100]
        checks = await asyncio.wait_for(jobicy_status(batch), timeout=45) if batch else {}
        feed.recheck_cursor = (offset + len(batch)) % len(pending) if pending else 0
        feed.availability = checks
    except Exception as exc:
        feed.error = "Availability check: " + type(exc).__name__
    return feed


async def refresh_jobs():
    global _status
    if _lock.locked():
        return jf.get_all_jobs()
    async with _lock:
        client, owner, acquired = None, str(uuid4()), False
        run_started, outcomes, run_id = False, {}, str(uuid4())
        sources, selected = {}, {}
        try:
            # Reloading never clears the last-good snapshot on database failure.
            await jf.reload_snapshot()
            client = jf._get_supabase_client()
            acquired = bool((await db_call(lambda: client.rpc("claim_job_refresh", {"p_owner": owner, "p_seconds": 600}).execute())).data)
            if not acquired:
                return jf.get_all_jobs()
            rows = (await db_call(lambda: client.table("job_ingestion_state").select("sources").eq("id", "global").execute(), attempts=3)).data
            sources = dict(rows[0].get("sources") or {}) if rows else {}
            _status = {**_status, "sources": sources, "error": None}
            if not _status.get("last_completed_at"):
                runs = (await db_call(lambda: client.table("job_fetch_runs").select("completed_at").order("started_at", desc=True).limit(1).execute(), attempts=3)).data
                if runs:
                    _status["last_completed_at"] = runs[0].get("completed_at")
            if any(item.get("last_success_at") for item in sources.values()):
                jf._refresh_finished = True
            providers = {"remoteok": (jf.fetch_remoteok_jobs, 6), "remotive": (jf.fetch_remotive_jobs, 6),
                         "himalayas": (_himalayas, 24), "jobicy": (_jobicy, 6)}
            if settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY:
                providers["adzuna"] = (_adzuna, 6)
            now = datetime.now(timezone.utc)
            selected = {name: task for name, task in providers.items() if due(name, sources, now)}
            if not selected:
                return jf.get_all_jobs()
            _status["running"] = True
            # Reserve attempts durably before calling providers; restarts cannot
            # replay quota-consuming requests that were already attempted.
            for name, (_, hours) in selected.items():
                sources[name] = {**sources.get(name, {}), "status": "running", "last_attempt_at": now.isoformat(),
                                 "next_due_at": datetime.fromtimestamp((int(now.timestamp()) // (hours * 3600) + 1) * hours * 3600, timezone.utc).isoformat()}
            await db_call(lambda: client.table("job_ingestion_state").update({"sources": sources}).eq("id", "global").eq("lease_owner", owner).execute(), attempts=3)
            await db_call(lambda: client.table("job_fetch_runs").insert({"id": run_id, "started_at": now.isoformat(), "status": "running", "sources": sources}).execute())
            run_started = True
            _status = {**_status, "running": True, "sources": sources}
            checkpoint_lock = asyncio.Lock()

            async def checkpoint():
                # Entire JSON source maps must arrive in order, or an older
                # concurrent write can replace a newer provider's outcome.
                async with checkpoint_lock:
                    snapshot = dict(sources)
                    await db_call(lambda: client.table("job_ingestion_state").update({"sources": snapshot}).eq("id", "global").eq("lease_owner", owner).execute(), attempts=3)

            async def run_source(name, fetch):
                try:
                    feed = await fetch()
                    fresh = {job.id: job for job in feed if jf._is_relevant_job(job)}
                    await jf.persist_jobs_to_supabase(list(fresh.values()))
                    # Publish only after successful persistence, keep every other
                    # provider's last-good data even when this pass is partial.
                    checks = getattr(feed, "availability", {})
                    for availability in ("active", "closed", "unknown"):
                        ids = [job_id for job_id, value in checks.items() if value == availability]
                        if ids:
                            value = availability
                            await db_call(lambda ids=ids, value=value: client.table("jobs").update({"availability": value}).in_("id", ids).execute(), attempts=3)
                    # Merge only after awaited writes, so another provider's
                    # intervening publication cannot be replaced by a stale map.
                    existing = {job.id: job for job in jf._job_store.values()}
                    existing.update(fresh)
                    for job_id, value in checks.items():
                        if job_id in existing:
                            existing[job_id] = existing[job_id].model_copy(update={"availability": value})
                    jf.publish_snapshot(existing.values())
                    error = getattr(feed, "error", None)
                    outcome = {**sources[name], "status": "partial" if error or getattr(feed, "capped", False) else "success",
                               "last_success_at": datetime.now(timezone.utc).isoformat(), "observed": len(fresh),
                               "coverage_capped": getattr(feed, "capped", False), "error": error}
                    if hasattr(feed, "recheck_cursor"):
                        outcome["recheck_cursor"] = feed.recheck_cursor
                except Exception as exc:
                    # Do not expose exception text: provider URLs can contain keys.
                    logger.warning("Job provider %s failed: %s", name, type(exc).__name__)
                    outcome = {**sources[name], "status": "failed", "error": type(exc).__name__}
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                        retry_after = exc.response.headers.get("Retry-After", "")
                        try:
                            retry_at = datetime.now(timezone.utc) + timedelta(seconds=int(retry_after)) if retry_after.isdecimal() else parsedate_to_datetime(retry_after)
                            if retry_at > parse_date(outcome["next_due_at"]):
                                outcome["next_due_at"] = retry_at.isoformat()
                        except (ValueError, TypeError, OverflowError):
                            pass
                sources[name] = outcome
                outcomes[name] = outcome
                try:
                    await checkpoint()
                except Exception as exc:
                    # Finalization retries the complete state. A failed status
                    # checkpoint must not cancel unrelated provider requests.
                    logger.warning("Provider %s checkpoint failed: %s; will finalize complete state", name, type(exc).__name__)

            try:
                async with asyncio.timeout(settings.JOB_REFRESH_TIMEOUT_SECONDS):
                    tasks = [asyncio.create_task(run_source(name, fetch)) for name, (fetch, _) in selected.items()]
                    try:
                        await asyncio.gather(*tasks)
                    finally:
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
            except TimeoutError:
                for name in selected:
                    if name not in outcomes:
                        sources[name] = {**sources[name], "status": "failed", "error": "Run deadline exceeded"}
                _status["error"] = "Refresh deadline exceeded; previous jobs retained"
            jf._refresh_finished = any(item.get("last_success_at") for item in sources.values())
            return jf.get_all_jobs()
        except Exception as exc:
            logger.exception("Job refresh coordinator failed")
            _status["error"] = type(exc).__name__
            return jf.get_all_jobs()
        finally:
            ended = datetime.now(timezone.utc).isoformat()
            if client and acquired:
                for name in selected:
                    if sources[name].get("status") == "running":
                        sources[name] = {**sources[name], "status": "failed", "error": "Coordinator interrupted"}
                if run_started:
                    run_status = "success" if all(item.get("status") == "success" for item in outcomes.values()) and len(outcomes) == len(selected) else "partial"
                    try:
                        await db_call(lambda: client.table("job_fetch_runs").update({"completed_at": ended, "status": run_status, "sources": sources}).eq("id", run_id).execute(), attempts=3)
                    except Exception:
                        logger.exception("Could not finalize job refresh history")
                        _status["error"] = "Refresh history persistence failed"
                # Always attempt lease release, even if run-history storage fails.
                try:
                    await db_call(lambda: client.table("job_ingestion_state").update({"sources": sources, "lease_until": ended, "lease_owner": None, "updated_at": ended}).eq("id", "global").eq("lease_owner", owner).execute(), attempts=3)
                except Exception:
                    logger.exception("Could not finalize ingestion state; lease expires automatically")
                    _status["error"] = "Ingestion state persistence failed; lease expires automatically"
            _status = {**_status, "running": False, "last_completed_at": ended if run_started else _status.get("last_completed_at"),
                       "sources": sources if acquired else _status.get("sources", {})}
