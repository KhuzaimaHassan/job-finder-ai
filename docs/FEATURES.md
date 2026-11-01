# Features and limitations

[Back to documentation](../README.md)

- Google sign-in through Supabase Auth; protected dashboard, profile, resume, and tracker pages.
- Search by keyword, location, source, work arrangement, and employment type. Remote and Full-time can be combined.
- Resume upload: text-based PDF, maximum 10 MiB, with structured Gemini parsing. Scanned PDFs require OCR outside this application.
- Matching: up to 100 keyword-shortlisted candidates ranked with embeddings, with a labelled keyword fallback if the AI provider fails or times out. Scores are relevance estimates.
- AI tools: resume/job compatibility estimate, cover letter, skill-gap analysis with reviewed learning resources, interview preparation, and resume suggestions.
- Tracker stages: Saved → Applied → Interview → Offer → Rejected. Desktop dragging, mobile status controls, and persistent notes are supported.
- Resume synchronization adds skills while preserving manually entered experience years and target roles. Replacement uploads retain previous saved versions.

All job AI tools use the uploaded resume; skills-gap and interview preparation
also include saved profile skills. Prompts receive the current UTC date to
interpret career dates, distinguish internships from employment, and avoid
inventing availability or credentials. Compatibility percentages are AI estimates
and are not scores from an employer's ATS. Review generated text before using it.
Structured tools request JSON object schemas from Gemini. ATS enrollment-status
claims use neutral qualification-review wording rather than publishing an
unverified inference about whether someone is currently studying.
Learning links come from a reviewed publisher catalog; a workflow-specific gap
uses its matching resource rather than a tutorial for an incidental language.
Structured application-tool quota exhaustion is returned as HTTP 429 with an actionable message;
temporary outages and timeouts use 503/504. The app does not automatically change
plans or retry quota failures. The Gemini project's configured limits apply to
resume parsing and generation across all users.
Resume parsing currently reports parser/provider failures as HTTP 500; see the
[operations guide](OPERATIONS.md) for this remaining error-mapping limitation.

Resume uploads succeed only after both the private PDF and parsed data are saved.
A storage failure returns HTTP 503 and preserves the previous resume. The Resume
page warns when a legacy record contains parsed text without a stored PDF; upload
the original again after configuring storage. Parsed text cannot recreate that PDF.

## Known limitations and next work

The release enforces freshness, expiry and history preservation, records durable runs and source budgets, and verifies search/matching behavior. **Sustained operation within the Render Free instance's memory limit remains unresolved.** Discovery is still bounded and source availability is external; full catalogue traversal, complete geocoding/eligibility, an exact schedule SLA, and a sustainable automatic Pakistan feed remain outside this implementation. The current Gemini chat SDK also needs migration. See [JOB_FETCHING.md](JOB_FETCHING.md), [OPERATIONS.md](OPERATIONS.md) and [VERIFICATION.md](VERIFICATION.md) for current behavior and validation limits.

For source coverage and freshness rules, see [job fetching and matching](JOB_FETCHING.md).
