"""
Job Finder — FastAPI Backend
-----------------------------
Main application entry point. Sets up CORS, routes, and a background
scheduler that refreshes jobs from all APIs every 6 hours.
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

from app.config import settings
from app.routers import jobs, auth, resume, profile, ai, applications
from app.services.job_fetcher import fetch_all_jobs, reload_snapshot, cache_ready
from app.services.ingestion import status as ingestion_status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm search before readiness; durable budgets determine which sources are due."""
    try:
        await asyncio.wait_for(reload_snapshot(), timeout=8)
    except Exception:
        logger.warning("Job snapshot is warming; readiness will return 503 until loaded")
    initial = asyncio.create_task(fetch_all_jobs())
    scheduler.add_job(fetch_all_jobs, "interval", minutes=1, id="refresh_jobs", max_instances=1, coalesce=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
    initial.cancel()
    try:
        await initial
    except asyncio.CancelledError:
        pass


_is_prod = os.getenv("RENDER", "") != "" or os.getenv("ENVIRONMENT", "").lower() == "production"

app = FastAPI(
    title="Job Finder API",
    description="AI-powered job aggregator with resume matching",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://job-finder-ai-kappa.vercel.app",
        "https://ai-jobfinder.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Register routers
app.include_router(jobs.router)
app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(profile.router)
app.include_router(ai.router)
app.include_router(applications.router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    from app.services.job_fetcher import get_all_jobs
    return {
        "status": "healthy" if cache_ready() else "warming",
        "ready": cache_ready(),
        "jobs_cached": len(get_all_jobs()),
        "revision": os.environ.get("RENDER_GIT_COMMIT", "local"),
    }


@app.get("/api/ready")
async def readiness():
    data = ingestion_status()
    return JSONResponse(data, status_code=200 if data["ready"] else 503)
