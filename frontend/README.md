# Job Finder AI frontend

Next.js 16.2 / React 19.2 client for the Job Finder API. Use Node.js 20.9+; Node 22 is recommended.

## Run locally

From `frontend/`:

```bash
npm ci
cp .env.local.example .env.local
# PowerShell: Copy-Item .env.local.example .env.local
npm run dev
```

Configure `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The browser key must be the public anon key. Start the backend separately and allow the local `/dashboard` OAuth redirect in Supabase. These public values are embedded during the build, so rebuild after changing deployment values.

Pages: `/dashboard`, `/job/[id]`, `/applications`, `/resume`, `/profile`, `/login`. The root redirects to `/dashboard`; protected pages wait for authentication initialization. OAuth returns to `/dashboard`.

```bash
npm run lint
npm run build
npm start
```

Vercel uses this directory as the project root. The production `X-App-Revision` header identifies the deployed Git commit.

The dashboard reads the backend snapshot when it requests jobs; it does not stream newly imported jobs. Its source date is not a guarantee that the employer is still accepting applications. See the [main README](../README.md), [job freshness guide](../docs/JOB_FETCHING.md), and [verification record](../VERIFICATION.md) for setup, limits and the disposable local browser fixture.
