# Job fetching, search and personalized matching

This guide describes the ingestion/search implementation. The earlier [28 October audit](job-freshness-audit-2026-10-28.json) and [startup sample](job-freshness-startup-2026-10-28.json) are historical evidence of the previous implementation, not current live totals.

## Freshness and history

- Search and matching require a parseable source publication/update date within `JOB_POSTED_MAX_AGE_DAYS` (default 30), a nonexpired `expires_at`, and no confirmed closed/unknown availability state.
- These checks run **on every read**, not only during refresh. An expired listing disappears from counts, search, and matching even between runs.
- The last observation must also be within `JOB_CACHE_MAX_AGE_DAYS` (default 14) when present. Publication age and observation age are separate clocks.
- A newly returned old posting does not bypass the source-date window. Missing/unparseable source dates are retained in storage but excluded from discovery.
- Source dates have different meanings: Himalayas `pubDate` means last updated. The UI says “dated or updated,” not “first published.” Employer availability can still change before a provider reports it.
- Rows are retained for saved-job history. Neither the cloud coordinator nor the standalone scraper hard-deletes them. Archived detail views disable Apply.
- The independent scraper's former `delete_old_jobs` entrypoint is now a compatibility no-op. User-entered tracker notes/status are unaffected.

`first_seen_at` records the import-time observation baseline; existing rows received the migration default, so it must not be presented as their original publication date. `fetched_at` is the last successful importer observation. Provider identity, employment type, source attribution URL, restrictions, expiry and availability survive restarts.

## Refresh coordination and schedule

The API warms its snapshot from Supabase before declaring readiness when possible. It checks refresh state each minute while running; **that does not mean it calls providers each minute**.

A database RPC atomically claims a bounded global lease. `job_ingestion_state.sources` persists per-source attempts, next due times, last successes, outcome/count, errors and coverage caps. Attempts are reserved before requests, so a restart cannot immediately replay a consumed provider slot. `job_fetch_runs` stores durable run outcomes. A lease eventually expires if a process crashes.

Providers other than Himalayas use UTC six-hour slots; Himalayas uses one UTC daily slot because its feed refreshes daily. The GitHub workflow [job-refresh.yml](../.github/workflows/job-refresh.yml) runs at 00:23, 06:23, 12:23 and 18:23 UTC, and can also be manually dispatched. It makes public readiness requests to wake a sleeping API and waits for the due coordinator work to settle. It uses no Supabase credentials or privileged HTTP refresh endpoint. Both GitHub's run log and the database retain outcomes.

GitHub scheduled execution is best effort: delays, disabled Actions, service outages, and inactive-repository schedule suspension still matter. This is not a strict six-hour SLA. An awake API catches up due slots on its minute tick; a restarted API reads the durable budget. For an exact uptime/SLA requirement, move to a supervised always-running ingestion worker or a supported dedicated scheduler.

The coordinator bounds the provider-work phase (`JOB_REFRESH_TIMEOUT_SECONDS`, default 240) and provider traversal (`JOB_PROVIDER_MAX_PAGES`, default 5); initial database reads and finalization add overhead outside that phase. It publishes newly fetched source records **after successful persistence**, retains other sources and prior data on failures, and never treats absence from a partial/capped feed as confirmed closure. Reads also enforce age/expiry against last-good data, so an outage does not keep jobs searchable indefinitely.

Snapshot reads, provider-ID upserts and idempotent status updates retry transport
failures up to three times with bounded backoff. Lease claims and run inserts are
not automatically replayed. Source checkpoints are serialized to prevent older
JSON maps overwriting newer outcomes. An exhausted checkpoint retry does not
cancel other providers; finalization retries the complete state. Run-history
storage and lease release are attempted separately, with failures surfaced in
status. Availability updates merge into the latest snapshot after awaited writes
so another provider's newly published jobs are retained.

## Provider behavior

| Provider | Discovery | Refresh / failure behavior |
| --- | --- | --- |
| RemoteOK | One public feed; technology-role filtering | Six-hour UTC slots; bounded transient retries |
| Remotive | **One broad public feed**, filtered locally | Six-hour UTC slots; no burst of 15 searches and no immediate retry storm |
| Himalayas | Five targeted newest-first searches; sequential pages, stable guid IDs | Daily UTC slot; explicit expiry persisted; bounded partial coverage reported |
| Jobicy | Canonical `/api/jobs` with sequential opaque cursor traversal | Six-hour slots; stored numeric IDs checked through `/api/jobs/status` in batches up to 100 |
| Adzuna | GB/US/India remote-themed searches, newest first, provider age filter, bounded pages | Optional credentials; six-hour slots; no Pakistan query |
| Indeed / LinkedIn | Separate optional manual importer | Not automatically fetched by the standard cloud requirements |
| JSearch | Not enabled | Quota/operating-budget decision remains separate |

Jobicy `closed` is archived; `unknown` is hidden without claiming confirmed closure. A provider status check is not a live probe of an employer's ATS. Older Himalayas rows without preserved provider identity are withheld until observed with the richer metadata. Expiry and missing-ID handling do not assume a capped first feed is a complete catalogue.

429 responses stop that request pass. Where an HTTP `Retry-After` survives to the coordinator, its later deadline extends the normal next-due time. Transport/5xx retries are bounded with jitter; Remotive uses one attempt per slot. Errors are stored as categories, not raw credential-bearing URLs.

Coverage remains intentionally bounded, not exhaustive. Capped/partial outcomes are visible through status; the UI does not claim every vacancy on each provider is present. Primary references: [Himalayas API](https://himalayas.app/api), [Remotive API](https://github.com/remotive-com/remote-jobs-api), [Jobicy API](https://jobicy.com/jobs-rss-feed).

## Search behavior

- Multiple query terms must all appear across title, skill tags, company or description; quoted phrases remain phrases.
- Matching uses word boundaries and selected aliases (`ML` / machine learning, `AI` / artificial intelligence, PostgreSQL / Postgres). `mail` does not match `email`, and `R` does not match arbitrary words containing r.
- Title and tag hits rank ahead of description-only hits; source date and ID provide stable tie breaking.
- Keyword, source, location, work arrangement, employment type and recent-date filters combine. They work in both All Jobs and Matched for Me.
- All Jobs location filters search posting geography; personalized matching separately checks known candidate restrictions.
- Default discovery covers at most the configured 30-day source-date window. The UI offers last 7/14 days as narrower views.
- Same-title jobs at different locations/contracts remain distinct. Display duplicates normalize title commas and global remote synonyms, but preserve differing country/timezone restrictions and employment types; every observed provider ID remains stored for history.

`GET /api/jobs` uses `job_type`; the compatibility `/api/jobs/search` route uses `type`. Both accept `posted_within_days`. The personalized route accepts the same filters as `/api/jobs`.

## Matched for Me

Each request reads the authenticated user's latest saved profile and latest parsed resume using that user's JWT/RLS client. Database work and keyword ranking run off the async event loop.

1. Use entered skills plus resume skills (or extracted technology terms from raw text if structured skills are absent). Candidate names, employer names, and arbitrary project titles are not match qualifications.
2. Exclude known conflicts with candidate country and supported timezone restrictions. With a known candidate country, specific unresolved posting geographies are excluded rather than assumed worldwide. Common city/country forms and explicit provider restrictions are evaluated. A country is inferred from common country/city forms in the free-text location; this is not a complete geocoding system.
3. Require a real skill overlap, or a target-role overlap for a role-only profile. When target roles are supplied, require at least half the role terms to align with the title; generic engineer overlap and company-description boilerplate are insufficient. Zero-overlap jobs are not promoted by embeddings.
4. Weight technology coverage and target-role alignment. Adding an unrelated extra skill does not lower the same job's fit. Explicit experience requirements contribute a separate component; jobs requiring over two years beyond entered experience are excluded. Unstated numeric requirements are not guessed from employment counts. A conservative title-seniority rule also withholds senior/lead/manager titles below three entered years and principal/staff/head/director titles below seven; this prevents truncated postings bypassing experience guidance. Talent-pool/community postings are excluded from vacancies. Use All Jobs to review broader opportunities.
5. Shortlist up to `MATCH_CANDIDATE_LIMIT` (default/max 100) deterministically. Both successful AI and fallback mode use this same bounded candidate set, so pagination does not switch between 100/200 candidates on provider failure.
6. If embeddings succeed within the deadline, combine 80% profile fit with 20% semantic similarity. Otherwise return the profile-based ordering and label it **Profile Match**. Every result explains matching skills, other listed technologies, role fit and known experience/location considerations. Listings mentioning postgraduate qualifications receive an explicit review note because a skills-only profile does not verify degrees.

These percentages estimate relevance; they are not probabilities, certified ATS scores, or a claim the candidate satisfies every requirement. Location is free text and minimum-experience extraction recognizes common explicit phrasing only. Employers' eligibility requirements still need checking. Keep the entered experience field current; resume job counts do not overwrite it. Updating profile details changes scoring immediately; embedding cache keys include the current profile/resume content.

## Readiness and operations

| Endpoint | Meaning |
| --- | --- |
| `/api/health` | Process response, revision, cached count, and readiness boolean |
| `/api/ready` | 200 when the snapshot is usable; 503 while warming; includes sanitized ingestion state |
| `/api/jobs/status` | Public sanitized source/run status and freshness windows |
| `/api/jobs/stats` | Current searchable counts after read-time policy |

Job-list/matching requests return 503 during initial warming rather than presenting a completed empty result. The frontend retries warming responses and shows refresh/partial-source information. Historical data and expired jobs remain in storage; no unreviewed storage-retention deletion runs.

On a new installation run [supabase_setup.sql](../supabase_setup.sql). On an existing installation apply [20261028_ingestion.sql](../backend/migrations/20261028_ingestion.sql) before deploying this release. It adds metadata and private ingestion tables/RPC, preserves all existing user/jobs data, and grants the lease only to `service_role`. No administrative ingestion secret is sent to the browser or GitHub workflow.

The [Render free-instance limitations](https://render.com/docs/free) still affect latency when waking a sleeping service. Multiple API processes have separate snapshots, but the shared database lease/budgets prevent duplicate provider runs; minute reloads bring each cache up to date. Only start one local fixture per test port.

Read-only diagnostics, from `backend/`:

```bash
python scripts/audit_freshness.py
python scripts/audit_freshness.py --database --output ../freshness-report.json
```

The optional database comparison reads the configured public jobs table; confirm it belongs to the same API. No job ingestion or mutation is triggered by this audit tool. It scans at most 50,000 rows and reports that cap. Multi-page reads are not a cross-request database snapshot.

For scheduled-run investigation, use the GitHub workflow log and the private `job_fetch_runs` / `job_ingestion_state` records. A healthy HTTP response alone does not certify all providers refreshed successfully. Test evidence and outstanding provider/environment limits belong in [VERIFICATION.md](../VERIFICATION.md).

The verification workflow keeps genuine provider failures red and prints source
error categories without waiting for buffered output. Re-running verification
does not clear historical failed-source state or bypass durable provider
cooldowns. After a failed attempt, the failed state remains visible until the
next eligible source refresh completes; an old failed Actions run remains in
GitHub's history after a fix.
