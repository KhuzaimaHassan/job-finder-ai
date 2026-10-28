# Reliability and responsive UI — verification

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
| Backend regression suite | 20 tests passed |
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

## Responsive UI and product corrections

- Mobile navigation keeps all four destinations available; typography uses Geist with a system fallback. Interactive controls have visible focus and touch-friendly spacing.
- Profile fields, upload actions, job headers, AI panels and dialogs adapt to narrow phones. Wide preformatted job content scrolls inside its container.
- Tracker uses a stage-filtered card list on phones and a horizontally scrolling board from tablet width. Status menus work without dragging; notes have a native editor, persistence, and error handling. Desktop keyboard dragging was verified after enabling the dedicated button handle.
- Remote and employment type filters combine independently. Employment terms and skill tags use token boundaries; explicit office requirements override remote-board defaults.
- Resume synchronization merges skills while preserving manually entered experience years and target roles.
- Tracker writes update timestamps, maintain actual application dates, and use deterministic UUID primary keys for concurrent duplicate-save protection without a schema migration.
- Skill-gap analysis receives the job description and offers only reviewed official resource URLs. AI input is treated as untrusted reference material and parsed data is validated.
- Setup SQL includes jobs, a private PDF storage bucket and user-folder policies for new installations. This SQL was reviewed but was not executed against production; the release uses existing schema columns.

Additional checks on 28 October 2026:

| Check | Result |
| --- | --- |
| Phone widths 320 and 375, tablet 768, desktop 1440 | No page-level horizontal overflow on the reviewed layouts; board/code overflow remains internal |
| Mobile navigation and profile | Navigation works; explicit Add buttons and save feedback work; values survive reload |
| Combined Remote + Full-time filters | Correct two matching fixtures, excluding the part-time job |
| Long title/company and wide code block | Wrapped title/company, stacked actions, internally scrolling code at 320px |
| Phone tracker notes/status/filter | Multiline notes and status survive reload; empty-stage feedback works |
| Desktop keyboard drag | Applied to Interview persists after reload |
| Phone PDF upload and AI panels | PDF extracted; all four panels render; interview answer expands; Escape closes modal |
| Resume sync | Six years and Platform Engineer preference preserved; SQL/FastAPI added |
| Final browser console | No warnings or errors |
| Live Gemini parse and skill-gap smoke | Synthetic PDF parsed with typed fields; Docker gap returned the reviewed official Docker URL |

The browser fixture remains disposable and uses deterministic AI; live provider smoke tests are separate. Tests do not establish production OAuth, storage policies or authenticated mutations. JSearch has not been re-enabled and no paid provider quota has been changed.

Existing resume versions are retained rather than deleted. A separate explicit
retention/cleanup policy can be added later. Job search freshness defaults to 14
days since observation; it is not a guarantee that an employer still accepts an
application. The optional local Indeed/LinkedIn scraper still needs an operating
schedule outside the cloud API deployment.

Local browser builds embed fixture URLs. Rebuild normally with real environment
values before deployment; use `app.main:app`, never `tests.browser_app:app`, for the
production backend.

The existing Gemini chat SDK emits a deprecation warning. Live synthetic calls still pass; migration to the replacement SDK remains a separate maintenance item.
