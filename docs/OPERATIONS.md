# Operations and reliability

[Back to documentation](../README.md)

This guide describes the deployed application's checks and known operational
limits. Observations below are dated evidence, not a live status page.

## Service entry points

| Component | Entry point | Purpose |
| --- | --- | --- |
| Frontend | [ai-jobfinder.vercel.app](https://ai-jobfinder.vercel.app/) | Current production frontend |
| API process | [GET /api/health](https://job-finder-ai-backend.onrender.com/api/health) | Revision, readiness flag and searchable count; HTTP 200 alone does not mean ready |
| Search readiness | [GET /api/ready](https://job-finder-ai-backend.onrender.com/api/ready) | HTTP 200 when the snapshot is usable, 503 while warming |
| Provider state | [GET /api/jobs/status](https://job-finder-ai-backend.onrender.com/api/jobs/status) | Source outcomes, timestamps, errors and coverage flags |
| Catalogue | [GET /api/jobs/stats](https://job-finder-ai-backend.onrender.com/api/jobs/stats) | Current searchable counts by source |
| Automation | [Scheduled refresh workflow](../.github/workflows/job-refresh.yml) | Wakes the API and checks readiness/source failure state |

The previous `job-finder-ai-kappa.vercel.app` alias is retained in the backend
CORS allowlist. Configure Supabase OAuth redirects for every frontend alias you
actually use. Public frontend environment values are embedded at build time.

For a documentation-only merge, Render supports `[skip render]` in the merge
commit message to avoid an unnecessary backend rebuild/restart; see
[deploy controls](https://render.com/docs/deploys#skipping-an-auto-deploy).
In that case, compare the running API revision with the last intended code
release, rather than treating a later docs-only main commit as a failed rollout.

## Open memory incident — investigated 1 November 2026

**Status: startup/refresh mitigation implemented on 3 November 2026; the original
allocation-level cause and long-duration production memory stability remain unproven.**

Render confirmed that the backend exceeded its **512 MB RAM** limit on
31 October 2026 at **17:08:21 UTC / 10:08:21 PM PKT** and restarted. This occurred
after release [1bf2ffe](https://github.com/KhuzaimaHassan/job-finder-ai/commit/1bf2ffe5b28eb856c21803e8380dca31e3b85855).
The configured Free instance also has 0.15 CPU. Detailed application-memory
graphs were unavailable on that plan during the investigation.

During the 1 November investigation, `/api/health` responded with HTTP 200 but
reported `status: warming`, `ready: false` and `jobs_cached: 0` on that revision.
`/api/jobs/status` had no loaded source state. These observations establish that
the process responded; they do not establish usable search or permanent data loss.

Logs before the crash repeatedly reported skipped one-minute scheduler ticks
because an earlier refresh execution was still running. The 1 November code inspection found:

- The coordinator reloads the full job snapshot before checking provider budgets.
- Snapshot loading downloads full rows in 1,000-row pages and constructs a
  replacement in-memory snapshot. Additional freshness/expiry checks occur at
  read time, so some downloaded rows will never be shown.
- Initial warm-up times out after eight seconds. Thread-based database work can
  outlive cancellation, which needs investigation for overlapping allocations.

These remain **candidate contributors, not a confirmed allocation-level cause**.
On 3 November, current Render logs confirmed overlapping startup database loads:
the timed-out worker continued while a second worker started. Local loading of
the then-current catalogue took 101.9 seconds before the fix.

The mitigation shares one cancellation-shielded loader, reuses successful loads
for 15 minutes, filters stale/expired records before hydration, uses smaller pages,
and extracts skill tags without repeatedly stripping HTML for every known tag.
Only searchable records are retained in memory; database history is preserved.
Local read-only measurements with all API modules imported loaded 1,727 jobs in
19.37, 16.08 and 11.34 seconds across three reloads. The Windows process peaked at
172.8 MiB resident memory; 20 cached ticks took less than a millisecond and did
not reload the database. These are local measurements, not Render memory readings
or a concurrent PDF/AI load test. See [verification history](VERIFICATION.md).

Continue monitoring startup, provider refreshes, matching and PDF/AI requests
over sustained use. No plan upgrade or history deletion was made.

## How to interpret a check

| Signal | Interpretation / next check |
| --- | --- |
| `/api/health` responds | Process is reachable; inspect `ready`, `jobs_cached` and `revision` |
| `/api/ready` returns 503 | Search snapshot is warming; inspect logs and restart events if it persists |
| Source `status: failed` | Failed attempt; inspect safe error category and next eligible slot |
| Source `status: partial` | Some records were saved or traversal was bounded; inspect `error` and coverage separately |
| `coverage_capped: true`, `backfill_pending: true` | Further pages are queued within future scheduled source budgets |
| Successful deployment / matching revision | Correct code is deployed; this does not prove source freshness or memory stability |
| Memory-limit restart | RAM exceeded the instance budget; distinguish this from idle spin-down or monthly usage limits |

The current workflow succeeds when the API is ready, ingestion is not running,
source state exists, and neither a coordinator error nor a `failed` provider is
present. A partial source with an error can still pass. It does not require every
source to have refreshed during that run and does not perform a memory soak test.
The latest five inspected runs were successful during the 1 November investigation,
including [41280920630](https://github.com/KhuzaimaHassan/job-finder-ai/actions/runs/41280920630).
Those results do not close the memory incident.

For a read-only freshness report, from `backend/`:

```bash
python scripts/audit_freshness.py
```

Use `--database` only after confirming that the configured Supabase project
belongs to the API being inspected. Provider quotas and durable cooldowns still
apply; do not clear source state just to make a health check pass. See the
[fetching guide](JOB_FETCHING.md) for traversal and expiry behavior.

## Resume storage

For existing projects missing PDF storage, apply the reviewed additive
[20261031_resume_storage.sql](../backend/migrations/20261031_resume_storage.sql).
The bucket is private, accepts PDFs up to 10 MB, and restricts authenticated
access to each user's UUID folder. An administrator upload alone cannot verify
those user access policies.

Uploads require PDF storage and parsed-row persistence before success. A storage
failure returns 503 and preserves the previous saved resume. Database insert
failure also preserves the previous version and attempts to remove the unsaved
new object. Verify `pdf_stored`, the saved row and the stored bytes using an
authenticated account. Check cross-user and anonymous denial with disposable
test data, and remove only that data after testing.

Legacy rows can contain parsed text without an original PDF. The Resume page
warns about this; the owner must upload the original again. Parsed text cannot
reconstruct the original file. Resume parsing currently reports parser/provider
failures as HTTP 500, while structured application-tool generation has separate
quota/outage mappings; upload-specific provider error mapping remains follow-up work.

## Free-tier capacity

The 31 October audit verified Render Free, Vercel Hobby, Supabase Free and the
Gemini project's Free tier. This describes the selected plans at that time,
not unlimited resources or guaranteed future cost/availability.

- **Render:** idle spin-down affects latency; CPU/RAM capacity is separate from
  monthly instance hours and bandwidth. See [Free instance limitations](https://render.com/docs/free).
- **Supabase:** monitor database size, egress, storage and active-user usage in
  the correct project/organization. Frequent full-snapshot downloads can consume
  egress even if the database remains small.
- **Gemini:** project-wide quotas are shared by parsing, generation and matching
  users. Check the configured model's actual limits in AI Studio; generation and
  embedding allowances differ. See [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).
- **Vercel:** inspect both project and account usage because allowances may be
  shared with other deployments.

Do not expose service-role keys, bearer tokens, private resumes or credential-bearing
provider URLs in public incident reports. Record aggregate checks and sanitized
errors; keep account screenshots and raw diagnostic logs private.
