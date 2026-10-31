"""Loopback-only browser fixture. Never use this module as a deployment entrypoint.

Run from backend: venv/Scripts/python -m uvicorn tests.browser_app:app --host 127.0.0.1 --port 8000
It exercises the real routers with disposable storage and deterministic AI responses.
"""
import base64
import json
import time
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.routers import jobs, profile, resume, applications, ai, auth
from app.services import job_fetcher, ai_gemini, ingestion
from app.services.auth import get_current_user
from app.limiter import limiter
from tests.support import MemoryDB, make_pdf

USER_ID = "00000000-0000-4000-8000-000000000001"
USER = {"id": USER_ID, "aud": "authenticated", "role": "authenticated",
        "email": "local-test@example.invalid", "app_metadata": {"provider": "google"},
        "user_metadata": {"full_name": "Local Test Candidate"},
        "created_at": "2026-01-01T00:00:00Z"}


def encoded(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


ACCESS_TOKEN = encoded({"alg": "HS256", "typ": "JWT"}) + "." + encoded(
    {"sub": USER_ID, "aud": "authenticated", "role": "authenticated",
     "exp": int(time.time()) + 86400, "iat": int(time.time())}) + ".local-test-signature"
db = MemoryDB({"profiles": [{"user_id": USER_ID, "name": "Local Test Candidate",
    "email": USER["email"], "skills": [], "target_roles": [], "location": "Karachi", "experience_years": 0}]})
now = datetime.now(timezone.utc).isoformat()
for id, title, tags in [("local_python", "Python Engineer", ["Python", "SQL", "FastAPI"]),
                         ("local_data", "Data Scientist", ["Python", "Machine Learning"])]:
    db.rows.setdefault("jobs", []).append({"id": id, "title": title, "company": "Local Test Company",
        "location": "Remote", "description": "Build Python and SQL services with FastAPI. Requires testing, Docker and engineering experience.",
        "url": "https://example.invalid/apply", "source": "remoteok", "posted_date": now,
        "job_type": "remote", "tags": tags, "fetched_at": now, "salary": None})
db.rows["jobs"][0]["description"] += " This is a full-time role."
db.rows["jobs"][1]["description"] += " This is a part-time role."
db.rows["jobs"].append({**db.rows["jobs"][0], "id": "local_long",
    "title": "Senior Platform Engineer for Distributed Data and Machine Learning Infrastructure",
    "company": "Example Company With A Deliberately Long Name For Layout Verification",
    "description": "<p>Full-time engineering position. Python, Docker and SQL.</p><pre>" + "very_long_code_" * 40 + "</pre>",
    "tags": ["Python", "Docker", "SQL"]})
db.rows["jobs"].extend([
    {**db.rows["jobs"][0], "id":"local_java", "title":"Java Engineer", "description":"Build Java services. Full-time.", "tags":["Java"]},
    {**db.rows["jobs"][0], "id":"local_us", "title":"US Python Engineer", "location":"USA", "location_restrictions":["United States"]},
    {**db.rows["jobs"][0], "id":"local_old", "title":"Archived Python Engineer", "posted_date":(datetime.now(timezone.utc)-timedelta(days=60)).isoformat()},
    {**db.rows["jobs"][0], "id":"local_expired", "title":"Expired Python Engineer", "expires_at":(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()},
])
job_fetcher._job_store = {row["id"]: job_fetcher._job_from_row(row) for row in db.rows["jobs"]}
job_fetcher._get_supabase_client = lambda: db
for module in (profile, resume, applications, jobs):
    module.get_user_supabase = lambda _token: db
    module.get_supabase = lambda: db
settings.GEMINI_API_KEY = None  # fixture never contacts Gemini or cloud storage
ingestion._status = {"running": False, "last_completed_at": now, "sources": {
    "jobicy": {"status": "partial", "coverage_capped": True, "backfill_pending": True, "error": None}}}


async def parsed(text):
    return {"skills": ["Python", "SQL", "FastAPI"], "education": [], "projects": [],
            "experience": [], "summary": "Synthetic local resume"}


resume.parse_resume_with_gemini = parsed


ai_quota_exhausted = False


async def ats(*_args):
    if ai_quota_exhausted:
        raise ai_gemini.AIServiceError(429, "AI provider quota reached. Try again after the quota resets, or ask the site owner to review Gemini limits.")
    return {"score": 85, "matching_keywords": ["Python", "SQL"], "missing_keywords": ["Docker"],
            "verdict": "Local fixture: strong Python and SQL alignment."}


async def cover(*_args):
    return "I build Python services.\n\nMy SQL and FastAPI experience fits this role.\n\nI would welcome a conversation."


async def skills(*_args):
    return {"missing_skills": ["Docker"], "courses": []}


async def interview(*_args):
    return [{"question": "How would you test a Python API?", "answer_structure": "Discuss unit, integration and browser tests."}]


async def improve(*_args):
    return ["Quantify the impact of your Python services."]


ai_gemini.run_ats_score, ai_gemini.run_cover_letter = ats, cover
ai_gemini.run_skill_gap, ai_gemini.run_interview_prep = skills, interview
ai_gemini.run_resume_improve = improve

app = FastAPI(title="Local disposable browser fixture")
app.state.limiter = limiter
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)


async def local_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.credentials != ACCESS_TOKEN:
        raise HTTPException(401, "Local test session required")
    return {"id": USER_ID, "name": USER["user_metadata"]["full_name"], "email": USER["email"], "token": ACCESS_TOKEN}


app.dependency_overrides[get_current_user] = local_user
for router in (jobs.router, profile.router, resume.router, applications.router, ai.router, auth.router):
    app.include_router(router)


@app.get("/auth/v1/authorize")
def authorize():
    return RedirectResponse("http://localhost:3000/dashboard?code=local-disposable-code")


@app.post("/auth/v1/token")
async def token(request: Request):
    body = await request.json()
    if body.get("auth_code") != "local-disposable-code" and body.get("refresh_token") != "local-disposable-refresh":
        raise HTTPException(400, "Unknown test code")
    return {"access_token": ACCESS_TOKEN, "token_type": "bearer", "expires_in": 86400,
            "refresh_token": "local-disposable-refresh", "user": USER}


@app.get("/auth/v1/user")
def user():
    return USER


@app.post("/auth/v1/logout")
def logout():
    return {}


@app.get("/_test/resume.pdf")
def pdf():
    return Response(make_pdf(), media_type="application/pdf")


@app.post("/_test/resume-failure/{enabled}")
def fail(enabled: bool):
    if enabled: db.fail_insert.add("resumes")
    else: db.fail_insert.discard("resumes")
    return {"enabled": enabled}


@app.post("/_test/storage-failure/{enabled}")
def storage_fail(enabled: bool):
    db.storage.fail_upload = enabled
    return {"enabled": enabled}


@app.post("/_test/ai-quota/{enabled}")
def ai_quota(enabled: bool):
    global ai_quota_exhausted
    ai_quota_exhausted = enabled
    return {"enabled": enabled}


@app.get("/_test/snapshot")
def snapshot():
    return {"resume_versions": len(db.rows.get("resumes", [])), "files": len(db.storage.files),
            "applications": db.rows.get("applications", [])}
