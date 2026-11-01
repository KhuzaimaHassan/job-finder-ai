# Configuration

[Back to documentation](../README.md)

| Variable | Where | Meaning / default |
| --- | --- | --- |
| `SUPABASE_URL` | Backend | Supabase project URL |
| `SUPABASE_KEY` | Backend | Public anon key used with each user's JWT |
| `SUPABASE_SERVICE_KEY` | Backend only | Administrative reads and job-cache writes; never expose as `NEXT_PUBLIC_*` |
| `GEMINI_API_KEY` | Backend only | Enables resume parsing and AI tools; matching falls back to keywords without it |
| `GEMINI_AI_MODEL` | Backend | `gemini-2.5-flash` default |
| `GEMINI_EMBEDDING_MODEL` | Backend | `gemini-embedding-001` default |
| `MATCH_CANDIDATE_LIMIT` | Backend | Semantic shortlist, default 100, maximum 100 |
| `MATCH_TIMEOUT_SECONDS` | Backend | Semantic ranking deadline, default 20, maximum 40 |
| `JOB_CACHE_MAX_AGE_DAYS` | Backend | Maximum last-observation age, default 14; also enforced at read time |
| `JOB_POSTED_MAX_AGE_DAYS` | Backend | Source publication/update age cap, default 30 |
| `JOB_PROVIDER_MAX_PAGES` | Backend | Traversal budget per query, default 5, range 2–20; includes newest page and saved backfill |
| `JOB_REFRESH_TIMEOUT_SECONDS` | Backend | Whole-run deadline, default 240 seconds |
| `FRONTEND_URL` | Backend | Allowed frontend origin for CORS; the verified production aliases `ai-jobfinder.vercel.app` and `job-finder-ai-kappa.vercel.app` are also allowed |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Backend | Optional Adzuna credentials |
| `HIMALAYAS_API_KEY` | Backend only | Optional free key; anonymous API requests share a public allowance |
| `JSEARCH_API_KEY` | Backend | Unused by the scheduled aggregator while its calls remain disabled |
| `NEXT_PUBLIC_API_URL` | Frontend | `http://localhost:8000` locally; Render API origin in production |
| `NEXT_PUBLIC_SUPABASE_URL` | Frontend | Same Supabase project as the backend |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Frontend | Public anon key; never the service-role key |

The coordinator ticks once per minute, while durable UTC source slots limit actual provider requests. See the fetching guide for schedule and coverage limits. `NEXT_PUBLIC_*` values are embedded at build time, so changing them requires a frontend rebuild.
