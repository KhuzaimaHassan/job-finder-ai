"""
Embeddings Service
------------------
Uses Gemini text-embedding-004 for embedding generation when configured.
Falls back to keyword overlap matching when the API key is missing or calls fail.
"""

import json
import logging
import re
import numpy as np
from typing import Any, List

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory cache for embeddings
_user_embeddings: dict[str, list[float]] = {}
_job_embeddings: dict[str, list[float]] = {}

_BASIC_STOPWORDS = frozenset(
    """
    a an the and or but in on at to for of as by with from into through during
    including excluding vs via per is are was were be been being have has had do does did
    will would could should may might must can this that these those it its we our your they their
    """.split()
)


def _normalize_string_list(value: Any) -> List[str]:
    """Coerce profile/resume list fields to a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return _normalize_string_list(parsed)
            except json.JSONDecodeError:
                pass
        return [s] if s else []
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    s = str(value).strip()
    return [s] if s else []


def _as_list(val: Any) -> list:
    """Coerce Supabase JSON/array fields to a list."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip().startswith("["):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _terms_from_resume_raw_text(raw_text: str | None, max_terms: int = 80) -> set[str]:
    """Extract coarse keywords from stored resume text when structured fields are sparse."""
    if not raw_text or not isinstance(raw_text, str):
        return set()
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", raw_text.lower())
    terms: set[str] = set()
    for w in words:
        if w in _BASIC_STOPWORDS or len(w) < 3:
            continue
        terms.add(w)
        if len(terms) >= max_terms:
            break
    return terms


def _collect_match_terms(profile: dict, resume: dict | None) -> set[str]:
    """Terms used for keyword-based scoring (lowercased)."""
    terms: set[str] = set()
    for s in _normalize_string_list(profile.get("skills")):
        terms.add(s.lower())
    for r in _normalize_string_list(profile.get("target_roles")):
        terms.add(r.lower())
    if resume:
        for s in _normalize_string_list(resume.get("skills")):
            terms.add(s.lower())
        for exp in _as_list(resume.get("experience")):
            if isinstance(exp, dict):
                title = (exp.get("title") or "").strip()
                company = (exp.get("company") or "").strip()
                if title:
                    terms.add(title.lower())
                if company:
                    terms.add(company.lower())
        for proj in _as_list(resume.get("projects")):
            if isinstance(proj, dict):
                name = (proj.get("name") or "").strip()
                if name:
                    terms.add(name.lower())
        summary = resume.get("summary")
        if isinstance(summary, str) and summary.strip():
            blob = summary.lower()
            for chunk in re.findall(r"[a-z][a-z0-9+#.-]{2,}", blob):
                if chunk not in _BASIC_STOPWORDS:
                    terms.add(chunk)

    terms = {t for t in terms if len(t) >= 2}
    if not terms and resume and resume.get("raw_text"):
        terms = _terms_from_resume_raw_text(str(resume.get("raw_text")))
    return terms


def _keyword_match_score(terms: set[str], job: Any) -> float:
    """Score 0–100 from overlap between user terms and job text."""
    if not terms:
        return 0.0
    tags = getattr(job, "tags", None) or []
    if isinstance(tags, list):
        tag_str = " ".join(str(t) for t in tags)
    else:
        tag_str = str(tags) if tags else ""
    title = str(getattr(job, "title", "") or "")
    desc = str(getattr(job, "description", "") or "")
    blob = f"{title} {desc} {tag_str}".lower()

    hits = 0
    for term in terms:
        if not term:
            continue
        if term in blob:
            hits += 1
            continue
        # Allow hyphen/space variants for multi-word roles (e.g. "machine learning")
        compact = term.replace(" ", "")
        if compact and compact in blob.replace(" ", ""):
            hits += 1

    ratio = hits / max(len(terms), 1)
    return round(min(100.0, ratio * 100.0), 1)


def _rank_jobs_keyword_based(
    profile: dict,
    resume: dict | None,
    jobs: list,
    top_n: int,
) -> list[dict]:
    terms = _collect_match_terms(profile, resume)
    scored: list[dict] = []
    for job in jobs:
        scored.append(
            {"job": job, "match_score": _keyword_match_score(terms, job)},
        )
    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:top_n]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _embedding_vector_from_result(result: Any) -> list[float]:
    """Normalize google.generativeai embed_content return value."""
    if isinstance(result, dict):
        vec = result.get("embedding")
    else:
        vec = getattr(result, "embedding", None)
    if vec is None:
        raise ValueError("Unexpected embed_content response (no embedding vector)")
    return list(vec)


async def get_embedding(text: str) -> list[float]:
    """Generate embedding using Gemini text-embedding-004."""
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")

    import google.generativeai as genai

    genai.configure(api_key=settings.GEMINI_API_KEY)

    text = text[:8000]

    try:
        result = genai.embed_content(
            model="models/embedding-001",
            content=text,
        )
        return _embedding_vector_from_result(result)
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise ValueError(f"Failed to generate embedding: {e}")


async def get_user_embedding(user_id: str, profile: dict, resume: dict | None = None) -> list[float]:
    """
    Generate and cache an embedding for a user based on their profile + resume.
    """
    parts: List[str] = []
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    skills = _normalize_string_list(profile.get("skills"))
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")
    roles = _normalize_string_list(profile.get("target_roles"))
    if roles:
        parts.append(f"Target roles: {', '.join(roles)}")
    if profile.get("location"):
        parts.append(f"Location: {profile['location']}")
    if profile.get("experience_years"):
        parts.append(f"Experience: {profile['experience_years']} years")

    if resume:
        rs = _normalize_string_list(resume.get("skills"))
        if rs:
            parts.append(f"Resume skills: {', '.join(rs)}")
        if _as_list(resume.get("experience")):
            for exp in _as_list(resume.get("experience"))[:3]:
                if isinstance(exp, dict):
                    parts.append(
                        f"Experience: {exp.get('title', '')} at {exp.get('company', '')}",
                    )
        if _as_list(resume.get("projects")):
            for proj in _as_list(resume.get("projects"))[:3]:
                if isinstance(proj, dict):
                    parts.append(
                        f"Project: {proj.get('name', '')} - "
                        f"{str(proj.get('description', ''))[:100]}",
                    )

    user_text = "\n".join(parts) if parts else "Data science machine learning python developer"

    embedding = await get_embedding(user_text)
    _user_embeddings[user_id] = embedding
    return embedding


async def get_job_embedding(job_id: str, title: str, description: str) -> list[float]:
    """Generate and cache an embedding for a job."""
    if job_id in _job_embeddings:
        return _job_embeddings[job_id]

    job_text = f"{title}\n{description[:2000]}"
    embedding = await get_embedding(job_text)
    _job_embeddings[job_id] = embedding
    return embedding


async def compute_match_score(user_embedding: list[float], job_embedding: list[float]) -> float:
    """Compute match percentage (0-100) between user and job."""
    similarity = _cosine_similarity(user_embedding, job_embedding)
    score = max(0.0, similarity) * 100
    return round(score, 1)


async def rank_jobs_for_user(
    user_id: str,
    profile: dict,
    resume: dict | None,
    jobs: list,
    top_n: int = 50,
) -> list[dict]:
    """
    Rank jobs by match score for a user.
    Returns list of {job: Job, match_score: float}.
    """
    if not settings.GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY not set; using keyword-based job matching")
        return _rank_jobs_keyword_based(profile, resume, jobs, top_n)

    try:
        user_emb = await get_user_embedding(user_id, profile, resume)

        scored_jobs: list[dict] = []
        for job in jobs:
            try:
                job_emb = await get_job_embedding(job.id, job.title, job.description)
                score = await compute_match_score(user_emb, job_emb)
                scored_jobs.append({"job": job, "match_score": score})
            except Exception as e:
                logger.error(f"Embedding error for job {job.id}: {e}")
                scored_jobs.append({"job": job, "match_score": 0.0})

        scored_jobs.sort(key=lambda x: x["match_score"], reverse=True)
        return scored_jobs[:top_n]
    except Exception as e:
        logger.warning(
            "Embedding-based ranking failed (%s); falling back to keyword matching",
            e,
        )
        return _rank_jobs_keyword_based(profile, resume, jobs, top_n)


def clear_user_embedding(user_id: str):
    """Clear cached embedding when profile/resume changes."""
    _user_embeddings.pop(user_id, None)


def clear_job_embeddings():
    """Clear all cached job embeddings (call after job refresh)."""
    _job_embeddings.clear()
