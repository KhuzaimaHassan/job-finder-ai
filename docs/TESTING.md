# Testing and local verification

[Back to documentation](../README.md)

Backend regression suite (from `backend/`):

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Frontend (from `frontend/`, with your intended environment configured):

```bash
npm run lint
npm run build
```

See [VERIFICATION.md](VERIFICATION.md) for tested flows and limits. The live freshness audit is read-only:

```bash
cd backend
python scripts/audit_freshness.py
# Optional: also read the PUBLIC jobs table configured in backend/.env
python scripts/audit_freshness.py --database --output ../freshness-report.json
```

When using `--database`, confirm that the configured Supabase project belongs to the API being audited. The report contains aggregate public job data, scans up to 50,000 DB rows, and marks that limit if reached. It does not invoke the scheduler, scrape providers, change rows, or prove recurring execution from one sample. API pagination is not transactionally consistent if a refresh occurs mid-audit.

## Disposable local browser fixture

The fixture exercises the real API routers and PDF extraction with in-memory database/storage, simulated auth, and deterministic AI. It never writes to production. **Never deploy it.**

Terminal 1, from `backend/`:

```bash
python -m uvicorn tests.browser_app:app --host 127.0.0.1 --port 8000
```

Terminal 2, from `frontend/`, set these process variables before building:

```text
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_ANON_KEY=local-disposable-anon
```

Then run `npm run build` and `npm start`. On [localhost:3000](http://localhost:3000), Continue with Google uses the disposable provider. A synthetic PDF is available at `http://localhost:8000/_test/resume.pdf`. Restarting the fixture discards its data. Rebuild with real environment values before using the frontend with real services.
