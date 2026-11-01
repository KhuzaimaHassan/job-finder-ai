# API reference

[Back to documentation](../README.md)

The frontend attaches the current Supabase bearer token to authenticated requests.

| Route | Access | Purpose |
| --- | --- | --- |
| `GET /api/health` | Public | Liveness, readiness, cached count and deployment revision |
| `GET /api/ready` | Public | 200/503 readiness and ingestion state |
| `GET /api/jobs/status` | Public | Sanitized provider outcomes, times and coverage limits |
| `GET /api/jobs` | Public | Search; `q`, `location`, `job_type`, `employment_type`, `source`, `posted_within_days`, `page`, `per_page` (1–100) |
| `GET /api/jobs/search` | Public | Alias that uses `type` for work arrangement instead of `job_type` |
| `GET /api/jobs/stats` | Public | Current snapshot counts by source |
| `GET /api/jobs/{id}` | Public | Active detail or retained archived record |
| `GET /api/jobs/matched` | Bearer token | Personalized ranking; optional `page`, `per_page` (1–50) |
| `GET /api/auth/me` | Bearer token | Current authenticated user |
| `GET/PATCH /api/profile` | Bearer token | Read or update profile |
| `POST /api/profile/sync-from-resume` | Bearer token | Merge latest resume skills into profile |
| `GET /api/resume`, `POST /api/resume/upload` | Bearer token | Read latest parsed resume / multipart PDF upload |
| `GET/POST /api/applications` | Bearer token | Read / save applications |
| `PATCH/DELETE /api/applications/{id}` | Bearer token | Edit status/notes or remove an application |
| `POST /api/ai/{tool}` | Bearer token | `ats-score`, `cover-letter`, `skill-gap`, `interview-prep`, `resume-improve` |

Example: `GET /api/jobs?q=python&job_type=remote&employment_type=fulltime&page=1&per_page=20`. All Jobs queries match descriptions as well as titles. There is no privileged public “fetch now” endpoint. Source-date filters and sanitized run/source status are available.
