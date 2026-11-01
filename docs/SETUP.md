# Local setup

[Back to documentation](../README.md)

Use **Python 3.12** to match the deployed backend and **Node.js 20.9+** (Node 22 recommended). Optional providers and AI calls may require accounts or incur provider usage; no provider pricing allowance is guaranteed here.

## 1. Supabase and Google sign-in

1. For an existing installation apply [`backend/migrations/20261028_ingestion.sql`](../backend/migrations/20261028_ingestion.sql) before this release. For a new installation create or select a Supabase project. Review and run [`supabase_setup.sql`](../supabase_setup.sql) in its SQL editor. It creates `jobs`, `profiles`, `resumes`, `applications`, RLS policies, the signup profile trigger, and a private `resumes` PDF bucket with user-folder policies. Review policy changes before rerunning it on an existing project.
2. Enable Google in Supabase Authentication and configure the Google OAuth client for your Supabase callback URL.
3. Set the Supabase Site URL to your frontend URL and allow `http://localhost:3000/dashboard` for local OAuth redirects. Allow `https://ai-jobfinder.vercel.app/dashboard` for the current production frontend, or the equivalent URL for your deployment. Keep `https://job-finder-ai-kappa.vercel.app/dashboard` only if you also use that previous alias.
4. Keep the Supabase service-role key on the backend only. The browser uses the public anon key and the signed-in user's token. Jobs are publicly readable; user tables and resume objects use user policies.

For an existing project missing PDF storage, review and apply
[`backend/migrations/20261031_resume_storage.sql`](../backend/migrations/20261031_resume_storage.sql).
It provisions the private 10 MB PDF bucket and per-user folder policies without
deleting resume records. Verify storage through an authenticated upload; a
service-role upload alone does not verify user access policies.

## 2. Backend

From the repository root:

```bash
cd backend
python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows PowerShell instead: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# PowerShell instead of cp: Copy-Item .env.example .env
```

Set actual values in `backend/.env`, then run:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Local API docs: [localhost:8000/docs](http://localhost:8000/docs). OpenAPI/Swagger are disabled when `RENDER` is set or `ENVIRONMENT=production`.

## 3. Frontend

In another terminal, from the repository root:

```bash
cd frontend
npm ci
cp .env.local.example .env.local
# PowerShell instead of cp: Copy-Item .env.local.example .env.local
npm run dev
```

Set the frontend environment values before starting. Open [localhost:3000](http://localhost:3000).



See [configuration](CONFIGURATION.md) for all environment variables and defaults. For hosting, see [deployment](DEPLOYMENT.md).
