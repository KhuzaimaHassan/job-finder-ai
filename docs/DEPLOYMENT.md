# Deployment

[Back to documentation](../README.md)

This repository's existing integrations deploy changes merged to `main`:

- **Vercel:** root directory `frontend`; configure the three `NEXT_PUBLIC_*` variables.
- **Render:** root directory `backend`; `pip install -r requirements.txt`; production entrypoint `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Configure backend secrets and `FRONTEND_URL`. See [render.yaml](../render.yaml).
- **Release check:** compare the frontend `X-App-Revision` header and backend `/api/health` JSON `revision` with the intended deployed release. Documentation-only commits can skip a Render deploy and leave its last code revision running. Neither marker confirms ingestion health.
- **Scheduler:** the minute coordinator reads durable source budgets and leases. The GitHub scheduled readiness check wakes a sleeping web service at 00:23/06:23/12:23/18:23 UTC. Delayed Actions/service outages remain possible; inspect database run records and public status.
- **Manual scraper:** a separate optional importer, with no recurring Pakistan runner configured. Old records are retained and the API applies its shared freshness policy.

Use the [operations guide](OPERATIONS.md) to distinguish a responding process,
a usable search snapshot, provider freshness and memory stability. It also records
the open 31 October memory incident and the limits of scheduled verification.
