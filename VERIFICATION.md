# Major reliability fixes — verification

Verified locally on 28 October 2026 before pushing this change.

## Changes

- Declare the PDF extractor in backend requirements. Keep existing resume rows and PDFs when saving a replacement fails; new uploads use unique object paths.
- Use a native modal dialog so the closed AI popup cannot intercept clicks. Support Escape, focus trapping, and focus restoration.
- Wait for authentication initialization before mounting protected page content. Attach the current session token per API request and reset page state when the signed-in user changes.
- Normalize Himalayas Unix timestamps, use its current search endpoint, skip malformed/expired records individually, and derive stable IDs from upstream identity.
- Use a configurable supported embedding model with async batched requests, bounded candidate counts/timeouts, content-aware caches, and consistent labelled keyword fallback.
- Publish persisted jobs before slow external fetching, persist refreshed existing IDs, exclude rows not observed within the configured freshness window, and retain archived detail access for tracker history.
- Refresh resume text immediately after upload, reset previous resume-improvement state, clear stale search totals on errors, and render API validation errors as text.

## Checks passed

| Check | Result |
| --- | --- |
| Default Next.js production build (Turbopack) | Passed, including TypeScript and static page generation |
| ESLint | Passed |
| Backend regression suite | 12 tests passed |
| Real Himalayas API smoke | Three results parsed with valid dates |
| Real Gemini embedding smoke | Successful 3,072-dimensional embedding from synthetic text |
| Real PDF extraction + live Gemini parsing | Passed using a generated synthetic resume; no database writes |
| Browser: local test sign-in and profile reload | Saved profile remained populated; no 401 or console errors |
| Browser: job buttons and native modal | Both buttons received clicks; open, Escape, and focus restoration passed |
| Browser: application tracker | Added a disposable card, moved Saved to Applied using keyboard drag/drop, and confirmed persistence after reload |
| Browser: resume upload | Real PDF extraction succeeded; skills and Resume Improver appeared immediately |
| Browser: matching | Uploaded skills produced correctly labelled keyword matches |
| Browser: AI screens | ATS score, cover letter, skill gap, interview questions, and resume improvement rendered successfully |
| Browser: job-page reload | Resume context survived reload; no browser console errors |

The browser run used the **real frontend and API routers** with disposable in-memory
database/storage and deterministic local authentication/AI providers. It did not
write to the production Supabase project. Separate provider smoke tests contacted
Himalayas and Gemini using synthetic/public input. The browser fixture does not
establish deployed OAuth, deployed RLS, or production storage-policy correctness.

The regression tests also cover failed resume inserts preserving the previous row
and PDF, failed/timeout embedding requests falling back consistently, malformed
provider records, refreshed existing job persistence, archived tracker lookup, and
embedding cache invalidation by content.

## Deliberately deferred

Responsive layout and visual polish, typography, employment-type filtering, skill
tag quality, tracker notes/timestamps/idempotency, experience-year calculations,
and broader deployment/database provisioning remain for the next pass. JSearch
has not been re-enabled and no paid provider quota has been changed.

Existing resume versions are retained rather than deleted. A separate explicit
retention/cleanup policy can be added later. Job search freshness defaults to 14
days since observation; it is not a guarantee that an employer still accepts an
application. The optional local Indeed/LinkedIn scraper still needs an operating
schedule outside the cloud API deployment.

Local browser builds embed fixture URLs. Rebuild normally with real environment
values before deployment; use `app.main:app`, never `tests.browser_app:app`, for the
production backend.
