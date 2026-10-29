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

## Ingestion/search/matching follow-up

The user applied `backend/migrations/20261028_ingestion.sql`; backend read checks confirmed its metadata fields and private ingestion tables. A real concurrency smoke test on `claim_job_refresh` returned one winner and one refusal, then released only the test-owned lease. No jobs or user data were removed by that check.

The expanded backend suite passes 40 tests covering read-time expiry/source-age policy, word/phrase/alias search, combined filters, stable pagination, distinct-location records, explicit location/timezone conflicts, profile/resume-driven ranking, experience changes, bounded retries, partial pages, persisted budgets and last-good snapshot retention. Existing resume/tracker/AI reliability regressions remain included. Expected synthetic failure logs exercise fallback paths.

Local browser checks passed against the disposable API fixture: five valid discovery records, with old/expired records absent; Python/SQL/FastAPI in Karachi yields three matches, excluding Java-only and US-restricted jobs; Remote + Full-time + Python SQL yields two matched results; changing the saved profile to Java/Java Engineer immediately yields one Java match. Match reasons render and the browser console is clean. The frontend production build and TypeScript/ESLint checks passed before these browser checks; final small UI copy/status changes are checked again for release.

Public provider smoke checks: Himalayas parsed 20 requested records; canonical Jobicy cursor traversal parsed 159 relevant records within its cap. Remotive and RemoteOK encountered local connection errors, which are reported as failures instead of being mistaken for successful empty feeds. Live Render source outcomes must be inspected separately after deployment; local connectivity does not establish provider availability on Render.

With explicit authorization, the live profile was filled from the public portfolio: 27 published skills, four stated career-role areas and Karachi. The existing zero completed-years value was preserved because the public site documents internships under a completed year. Save/reload succeeded. No resume was uploaded or fabricated for that check.

Live validation follow-up: the first production browser run exposed high scores for principal-level short-description postings and unresolved city-only geography. A follow-up adds conservative seniority floors, city/country handling and excludes unresolved specific geographies from personalized matches. It also removes talent-pool posts from vacancy discovery. The workflow wait budget is extended to nine minutes inside its ten-minute job limit, since the first manually dispatched check ended before deployment plus initial ingestion finished. Missing cached Jobicy IDs are checked in a bounded, rotating batch; freshly returned feed IDs are already active and do not need redundant status calls.

The corrected scheduled workflow rerun succeeded. A further live list check showed unrelated support roles admitted by boilerplate skill mentions; target-role alignment is now required when roles are saved, postgraduate requirements are explicitly flagged as unverified, and title-comma/global-location synonyms are deduplicated without merging distinct restrictions. These cases have regression coverage.

## Live AI Co-Pilot follow-up

With the user's uploaded resume, all four tools returned live results for Askable's
AI coding role and Xperteez's ML research role; the resume improver also returned
five suggestions. This exposed quality defects despite successful requests:
past 2025/2026 experience was described as future-dated, cover letters asserted
unverified availability, interview questions conflated LLM use with coding
assistants, and a coding-assistant gap linked to a basic Python tutorial.

The follow-up adds the current UTC date and explicit evidence rules to provider
instructions, sends full resume evidence to skill-gap/interview endpoints, uses
a specific reviewed coding-assistant resource ahead of incidental language matches,
and labels compatibility percentages as estimates. Existing API callers can omit
the new resume fields. Regression coverage checks the provider context, resume
handoff, unrelated resource rejection and duplicate resource removal. Prompt rules
reduce unsupported output; generated text still requires user review.

A synthetic live Gemini check of the updated ATS prompt correctly treated June
2026 graduation and the 2025 internship as past events and distinguished the
experience requirement from demonstrated skills. The remaining synthetic checks
hit the configured Gemini free-tier daily limit (20 requests reported by the
provider). No billing or model plan was changed. Provider quota, outage and
timeout handling is covered with deterministic failures; further real-model
generation after the fix requires available provider quota.

Release validation: all 44 backend regressions pass; frontend lint and production
build pass. The local browser with a disposable synthetic resume renders all four
panels, expands the interview answer, clears results when changing jobs, and
displays the controlled quota failure with a usable retry button. Earlier console
entries from rebuilding the running frontend and replacing the fixture session
were resolved by restarting the frontend and signing into the disposable provider.

Post-deployment verification on 29 October found that the configured sign-in flow
lands on `ai-jobfinder.vercel.app`, while backend CORS allowed only the previous
production alias. Both frontends returned the same deployed revision. The exact
new origin is added to the allowlist; a regression verifies both aliases accept
authenticated-request preflights and unrelated Vercel origins remain rejected.

With quota available on 29 October, all four live tools returned results for both
jobs and the resume improver returned five suggestions. The revised cover letters
omitted unverified availability; the research-role skill gap used the reviewed
GitHub guide. Targeted review still caught an unsupported current-enrollment label
and a LangGraph/coding-assistant equivalence in an interview question. Shared
system instructions now explicitly constrain both cases, with the interview
system prompt additionally requiring development-tool examples for that workflow.

A targeted synthetic run also returned an invalid top-level interview shape and
repeated a current-enrollment inference despite prompt constraints. Structured AI
tools now request provider-enforced JSON object schemas. ATS verdicts containing
enrollment-status prose use neutral qualification-review wording instead of
publishing that inference; matching/missing requirements remain visible.
All 46 backend regressions pass. Targeted live synthetic checks returned a valid
five-question object distinguishing development assistants from LangGraph and an
ATS result preserving the MSc/PhD gap while neutralizing enrollment-status prose.
