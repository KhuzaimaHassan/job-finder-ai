"""
Job Finder — FastAPI Backend
-----------------------------
Main application entry point. Sets up CORS, routes, and a background
scheduler that refreshes jobs from all APIs every 6 hours.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.routers import jobs, auth, resume, profile, ai, applications
from app.services.job_fetcher import fetch_all_jobs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: fetch jobs immediately, then schedule refresh every 6 hours."""
    logger.info("Starting up — fetching jobs from all sources...")
    try:
        await fetch_all_jobs()
    except Exception as e:
        logger.error(f"Initial job fetch failed: {e}")

    scheduler.add_job(fetch_all_jobs, "interval", hours=6, id="refresh_jobs")
    scheduler.start()
    logger.info("Scheduler started — jobs will refresh every 6 hours")

    yield

    scheduler.shutdown()
    logger.info("Scheduler shut down")


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
        "status": "healthy",
        "jobs_cached": len(get_all_jobs()),
    }
