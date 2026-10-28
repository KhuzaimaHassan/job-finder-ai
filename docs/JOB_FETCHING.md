# Job fetching and freshness

This document describes the implementation on main at `ba61f2b`, audited on **28 October 2026**. The improvement plan below is proposed work, not deployed behavior. There is no separate product requirements specification in this repository; the README and implementation establish the current scope: remote technology jobs, Pakistan listings when an importer supplies them, fast search, personalized matching, and a tracker with historical links.

## Direct answers

| Question | Current answer |
| --- | --- |
| Does it use live jobs? | Yes. External provider APIs are queried on startup and during scheduled runs; searches use a cached snapshot. |
| Does it fetch only recently posted jobs? | No. There is no shared publication-age cutoff, and providers expose different date meanings. |
| Does it remove old batches? | There is no batch lifecycle. Stale observations are excluded on database reload; their rows remain stored in the cloud path. |
| Is every displayed job still accepting applications? | Not established. Last observation is not employer availability. |
| Does it refresh every six hours continuously? | Only while the API process is running. No durable scheduler or missed-run catch-up is configured. |
| Does it continuously fetch Pakistan listings? | Not with the standard deployment. JSearch is disabled and JobSpy is not in deployed requirements. |
| Is the design sufficient? | Useful MVP foundation; insufficient for a strict recent-jobs promise or a reliable unattended ingestion service. |

## Live evidence

The [warmed production audit](job-freshness-audit-2026-10-28.json) started at **2026-10-28 13:59:57 UTC**. It made GET requests to the deployed API and SELECT queries against the configured public jobs table. No ingestion, mutation, or cleanup was triggered by the audit tool.

| Measurement | Result |
| --- | --- |
| Served revision | `ba61f2b75e9572518bfcdf6c5e3038f093146451` |
| Searchable jobs | 324 |
| Source date within the previous day | 42 |
| Source date within the previous seven days | 184 |
| Source date older than 14 days | 107 |
| Source date older than 30 days | 61 |
| Oldest source date in search | 14 August 2025, Adzuna |
| Stored database rows | 7,305 |
| Database rows last observed more than 14 days earlier | 6,976 |
| Those stale database IDs present in search | 0 |
| Latest observation for all five cloud API sources | 28 October 2026, 13:58:45 UTC |
| Latest stored Indeed / LinkedIn observations | 18 May 2026 |
| Latest stored JSearch observation | 10 September 2026 |

The data proves a recent successful observation/write for each of the five cloud API sources. It does not prove six-hour execution during unattended periods, completeness of every source query, or employer acceptance of every job. Numbers change on subsequent runs. Source dates are interpreted as UTC when the source supplied a date without a timezone; some are only day-precision. Himalayas documents `pubDate` as its last update time, so this is not universally original-publication age.

A [startup sample](job-freshness-startup-2026-10-28.json), taken earlier at 13:57 UTC, returned `status: healthy` with **zero cached/searchable jobs**, while fresh database rows existed. The later sample had 324. The first attempt also experienced an API read timeout. This shows a startup-readiness gap; it does not by itself prove which Render instance plan is used or why a particular restart occurred.

### Searchable counts by source

| Source | Searchable | Source date older than 14 days |
| --- | ---: | ---: |
| Jobicy | 138 | 0 |
| Himalayas | 96 | 54 |
| RemoteOK | 63 | 37 |
| Adzuna | 16 | 9 |
| Remotive | 11 | 7 |

An old source date does not establish that a job is closed. A freshly observed listing can legitimately remain open for months. A “recently posted only” product promise needs a separate publication-age policy and clear date semantics.

## Current execution flow

The relevant code is [`main.py`](../backend/app/main.py), [`job_fetcher.py`](../backend/app/services/job_fetcher.py), [`job_normalization.py`](../backend/app/services/job_normalization.py), and the [Job schema](../backend/app/schemas/jobs.py).

1. FastAPI startup creates a background `fetch_all_jobs()` task and starts an in-process APScheduler interval of six hours. Requests can be served before that first task completes. This interval is measured from scheduler startup, not fixed wall-clock batch times.
2. `_load_persisted_jobs()` pages through Supabase in groups of 1,000, keeping rows whose `fetched_at` is at or after UTC now minus `JOB_CACHE_MAX_AGE_DAYS`. Rows that fail normalization are skipped. The location heuristic is applied.
3. On an empty in-memory store, the loaded rows are published before waiting for external APIs. The database load itself can still be slow or fail, so the cache is not guaranteed ready immediately.
4. `asyncio.gather(..., return_exceptions=True)` launches the configured API calls concurrently. Most calls have a 30-second HTTP timeout. A provider exception usually becomes an empty list plus a log message.
5. The optional in-process JobSpy helper is attempted after the HTTP tasks. The standard production requirements do not install it, so it skips there. Installing it can make this phase slow; no whole-run deadline is configured.
6. Location heuristics retain remote jobs and Pakistan jobs, reject some foreign onsite locations, and keep some ambiguous/unclassified listings. Remote-country and timezone eligibility for Pakistan are not fully evaluated.
7. Fresh provider results take precedence over database rows with the same ID. Remaining database rows inside the last-seen window are merged in. Missing provider results do not immediately close previously cached jobs.
8. Display results are deduplicated by trimmed, lowercased **title + company**. The first encountered result wins. This can collapse distinct locations or contracts with the same title and employer; it is not a canonical vacancy identity.
9. A new in-memory dictionary replaces the previous snapshot. This replacement avoids partially building a visible list, but it is not a database transaction or a guarantee of persisted success.
10. Freshly observed source IDs, including existing IDs, are upserted in groups of 200. Each gets a new `fetched_at`. Rows only reloaded from the database do not have their age renewed. Failed write groups are logged; no persisted run status or automatic retry queue records the partial failure.

Search, counts, and matching use the in-memory store. A user search does not cause new provider calls. The running frontend does not subscribe to background refresh completion; navigate, reload, or run another search to obtain the current snapshot.

### Date and status semantics

| Field/concept | Meaning now | What it does not prove |
| --- | --- | --- |
| `posted_date` | Provider date string; normalized numeric timestamp for Himalayas | Consistent original publication time across providers |
| `jobs.fetched_at` | Most recent importer observation written to Supabase | New posting, open employer application, or successful full-provider traversal |
| `JOB_CACHE_MAX_AGE_DAYS` | Which stored observations can be reloaded into active search | A maximum age from publication |
| `Job.is_active` | True for current in-memory jobs; False on archived database fallback | Independently verified open/closed status |
| `/api/health.status` | API process responds | Ready search data, working providers, or recent scheduled execution |

Example: a job published in August and returned again today gets today's `fetched_at` and remains searchable. A job last seen 15 days ago is excluded when the next database reload rebuilds the cache, but its stored row is retained. An observation can cross the 14-day boundary between refreshes and remain visible until the next completed rebuild. Reads do not re-evaluate a per-job clock.

## Provider coverage and operating constraints

The scheduled cloud pass makes **28 potential HTTP requests**: RemoteOK 1 + Remotive 15 + Himalayas 5 + Jobicy 4 + Adzuna 3. Adzuna skips without credentials. A long-lived process normally schedules four passes per day, plus a startup pass on every restart. This is not a usage budget guarantee.

- **RemoteOK:** one feed request. Broad substring relevance checks inspect titles/tags/description; this can include false matches. No explicit age cutoff or closure revalidation is applied.
- **Remotive:** 15 overlapping category/search requests, capped at 100 results each. The provider documents a public-feed delay and a low polling budget. Its guidance calls for about four fetches per day and blocks excessive per-minute use; the current concurrent burst needs consolidation. Prefer a cached broad fetch filtered locally, or a documented provider-agreed plan. [Official API guidance](https://github.com/remotive-com/remote-jobs-api).
- **Himalayas:** five targeted queries, page 1, at most 20 per query, no explicit `sort=recent`. The provider documents daily-refreshed data and page/cursor traversal. `expiryDate` is checked only during parsing, then discarded by this schema. A previously saved job can be reloaded within its last-seen window after expiry. The provider also offers a single-job availability endpoint. Preserve expiry/identity and use these fields when reconciling availability. [Official API documentation](https://himalayas.app/api).
- **Jobicy:** four capped requests to the existing v2 adapter. Current provider documentation describes cursor traversal and batch availability checks; neither is implemented here. A job disappearing from the provider's recent feed is not sufficient evidence of closure. [Official API documentation](https://jobicy.com/jobs-rss-feed).
- **Adzuna:** first page for three remote-themed queries in GB, US, and India; no Pakistan query. The text heuristic can confuse “remote” mentions with an actual work-arrangement guarantee. API credentials and provider quotas control availability.

These constraints mean six-hour application polling cannot promise jobs within six hours of an employer posting them. Follow source attribution/application-link requirements when changing adapters or display behavior; current source badges are labels rather than linked attribution on every card.

### Optional local scraper

[`backend/scripts/scrape_and_upload.py`](../backend/scripts/scrape_and_upload.py) is a separate manual importer for Indeed Pakistan searches and LinkedIn remote searches. It requires `python-jobspy` installed separately, working site access, and backend Supabase credentials. The scraper requests a seven-day window, but actual provider support and returned dates vary. It is not run by the deployment blueprint or a provisioned recurring job.

**Its current `delete_old_jobs(days=14)` call physically deletes all shared jobs rows older than the last-seen cutoff after a nonempty scrape, irrespective of source.** It does not check whether a tracker references the job. This conflicts with the cloud service's archive/history policy. Do not run it unchanged to implement retention. Unify the retention policy first; the read-only audit tool is safe to use instead. This audit did not execute the scraper or its cleanup.

Uploaded rows become visible when the backend next reloads persisted jobs. A redeploy triggers such a reload but should not become the normal ingestion mechanism.

## Assessment against the platform needs

| Platform need | Assessment |
| --- | --- |
| Fast search without per-user provider calls | Supported by shared in-memory snapshot; cold-start readiness remains a gap |
| Live inputs from several boards | Confirmed for five cloud sources in the dated audit |
| Strictly recent postings | Not implemented; last-seen TTL is a different policy |
| Remove unavailable jobs promptly | Partial; ingestion-time Himalayas expiry check, no general closure reconciliation |
| Avoid old search accumulation | Partial; 14-day last-seen reload window, no read-time expiry |
| Preserve saved-job history | Cloud archive lookup supports it; standalone cleanup conflicts |
| Continuous Pakistan coverage | No scheduled importer in the standard deployed dependencies |
| Complete discovery | No; capped first pages, overlapping queries, title/company deduplication |
| Correct candidate eligibility and role focus | Heuristic; country-restricted remote jobs and unrelated roles can remain |
| Recover gracefully from partial failures | Some timeouts/isolation and last-seen fallback; no durable per-source run outcome or retry budget |
| Operate across restarts or multiple instances | In-process scheduling and caches need a durable coordination design |
| Explain freshness to users/operators | Source dates exist; last successful refresh/readiness are not exposed |

## Prioritized improvements

These are recommended next changes and acceptance criteria, not hidden fixes in this documentation change.

1. **Preserve history consistently and track availability.** Remove the standalone importer's unconditional shared-table deletion. Store `first_seen_at`, `last_seen_at`, provider publication/update time, `expires_at`, canonical identity, and an explicit active/closed/unverified state. Hide confirmed expired jobs promptly. A partial feed's missing ID must not be marked closed automatically. Tracker history must survive every importer and cleanup path.
2. **Make scheduling and readiness observable.** Move ingestion to one durable scheduled worker with a lease/lock and per-source run records: start/end, success/failure/partial, counts, error category, and last success. Keep last-good data on failed runs. Add readiness distinct from liveness and show last refresh/partial-source state. Demonstrate execution through a restart and an unattended period; handle stale data without reporting a completed empty search at startup.
3. **Respect budgets and improve discovery.** Consolidate Remotive requests; use per-provider concurrency and request budgets, retries with jitter/`Retry-After`, cached feeds, and bounded page/cursor traversal. Newest-first queries need explicit source-supported ordering. Bound whole-run duration. Demonstrate no duplicate scheduler runs and stable snapshot publication under 429s, timeouts, and partial persistence failures.
4. **Agree the product freshness/eligibility policy.** Add an explicit recent-publication filter (for example configurable 7/30-day views) without equating an older open job with closure. Preserve unknown dates separately. Evaluate remote country/timezone restrictions, tighten role relevance with word-aware rules, and avoid merging distinct vacancies solely by title/company. Make the source's date meaning visible.
5. **Restore local-market coverage deliberately.** Choose a sustainable Pakistan provider/importer and a supervised runner. Review credentials, operating budget and site access before enabling it. Do not re-enable JSearch solely because a key exists.
6. **Define storage retention after archival works.** Agree how long to keep unreferenced archived jobs, protect referenced history or store a complete tracker snapshot, and provide a dry-run report before any deletion. There is currently no automated database size cap or retention schedule in the cloud path.

## Operations and troubleshooting

Use one API worker/instance while ingestion remains inside the API process. Each process would otherwise create its own scheduler and separate in-memory cache. Restarts reset the six-hour interval and launch an additional immediate fetch.

If the Render service uses a Free instance, idle spin-down interrupts in-process scheduling. The current plan was not verified by this audit. Use infrastructure that actually executes the agreed schedule; configure a durable scheduled job or an always-running worker as part of the scheduler improvement, rather than assuming a web process is continuously alive. [Render's instance limitations](https://render.com/docs/free).

| Symptom | Check |
| --- | --- |
| Healthy response, zero jobs | Startup warming or failed DB/provider load; compare later counts and logs; health is not readiness |
| Fewer jobs after the release | Old last-seen rows are excluded and title/company duplicates collapse; inspect date/source counts |
| Many old source dates | Current last-seen policy allows them when sources return them again |
| No Indeed/LinkedIn jobs | Their importer is separate, not scheduled in production; check observation timestamps before running anything |
| Remotive count unexpectedly small | Inspect HTTP 429s/invalid categories and reduce the concurrent burst; successful rows alone do not prove every query passed |
| New local imports not in search | Wait for the next DB reload; the API does not watch database changes |
| Search count differs from DB count | Expected from TTL, location filtering, deduplication, and retained history |
| Lost older tracker detail | Check whether the standalone cleanup physically deleted its jobs row |
| Provider request or batch write fails | Inspect logs; no durable run-status API exists yet |

Read-only diagnostics, from `backend/`:

```bash
python scripts/audit_freshness.py
python scripts/audit_freshness.py --database --output ../freshness-report.json
```

The optional database audit uses the public anon client and selects only public job identifiers/source/dates; it never needs a service-role key. Ensure `backend/.env` refers to the same Supabase project as the API. The tool retries one failed GET to accommodate startup, never calls `fetch_all_jobs`, and returns a nonzero exit code if a requested API/database read fails. A successful audit says reads worked; it does not certify freshness or employer availability. Audits read multiple pages without a cross-request snapshot, so a concurrent refresh may affect totals.

For scheduler investigation, inspect logs for `Starting full job fetch`, per-source failures/counts, `Total ... unique jobs cached`, persistence failures and final persistence counts. Compare source-specific stored `fetched_at` values over time. The current schema cannot reconstruct historical run outcomes, so one sample cannot certify schedule adherence.

## Verification limits

Existing regression tests verify stale observation exclusion, archival detail lookup, warm-data publication before slow providers, refreshed existing-ID persistence, malformed Himalayas record isolation and date normalization. They do not yet cover durable scheduling, source budget compliance, complete pagination, closure reconciliation, query-time expiry or the standalone scraper's destructive cleanup. See [VERIFICATION.md](../VERIFICATION.md) for broader local UI/API checks.
