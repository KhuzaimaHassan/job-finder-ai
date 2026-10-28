"""
Embeddings Service
------------------
Uses configurable Gemini embeddings when configured.
Falls back to keyword overlap matching when the API key is missing or calls fail.
"""

import json
import asyncio
import hashlib
import logging
import re
import httpx
import numpy as np
from typing import Any, List

from app.config import settings
from app.services.job_policy import term_matches, location_eligible, minimum_experience, parse_date, seniority_floor

logger = logging.getLogger(__name__)

# In-memory cache for embeddings
_user_embeddings: dict[str, tuple[str, list[float]]] = {}
_job_embeddings: dict[str, tuple[str, list[float]]] = {}

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
    # Employer names, candidate names and project names are not qualifications.
    skills = _normalize_string_list(profile.get("skills"))
    if resume:
        skills += _normalize_string_list(resume.get("skills"))
        if not skills and resume.get("raw_text"):
            from app.services.job_fetcher import _extract_tags
            skills = _extract_tags(str(resume["raw_text"]))
    return {skill.lower() for skill in skills if skill.strip()}


def _keyword_match_score(terms: set[str], job: Any) -> float:
    if not terms:
        return 0.0
    blob = f"{job.title} {job.description} {' '.join(job.tags)}"
    return round(100 * sum(term_matches(blob, term) for term in terms) / len(terms), 1)


def _profile_match(profile, resume, job):
    if not location_eligible(job, profile.get("location")):
        return None
    years = max(0, profile.get("experience_years") or 0)
    if years < seniority_floor(job):
        return None
    terms = _collect_match_terms(profile, resume)
    blob = f"{job.title} {job.description} {' '.join(job.tags)}"
    hits = sorted(term for term in terms if term_matches(blob, term))
    roles = _normalize_string_list(profile.get("target_roles"))
    def role_alignment(role):
        if term_matches(job.title, role):
            return 100.0
        words = re.findall(r"[A-Za-z][A-Za-z+#.]*", role)
        return 100 * sum(term_matches(job.title, word) for word in words) / max(1, len(words))
    role_score = max((role_alignment(role) for role in roles), default=0)
    if roles and role_score < 50:
        return None
    if (terms and not hits) or (not terms and role_score == 0):
        return None
    from app.services.job_fetcher import _extract_tags
    missing = [skill for skill in _extract_tags(blob) if not any(term_matches(skill, term) or term_matches(term, skill) for term in terms)]
    parts, reasons = [], []
    if terms:
        # Adding unrelated skills to a profile must not lower the same job fit.
        parts.append((60, len(hits) / max(1, len(hits) + len(missing)) * 100))
        reasons.append("Matching skills: " + ", ".join(hits[:6]))
        if missing:
            reasons.append("Other listed technologies: " + ", ".join(missing[:5]))
    if roles:
        parts.append((25, role_score))
        reasons.append("Target role aligns" if role_score >= 50 else "Limited target-role alignment")
    required = minimum_experience(job)
    if required is not None:
        if required > years + 2:
            return None  # Explicit minimum is materially beyond entered experience.
        parts.append((10, 100 if years >= required else years / required * 100))
        reasons.append(f"Experience: {years} years entered; listing asks for {required}+")
    if profile.get("location"):
        reasons.append("No known conflict with your entered location; check employer eligibility")
    if re.search(r"\b(?:PhD|MSc|doctorate|master['’]?s)\b", f"{job.title} {job.description}", re.I):
        reasons.append("Review postgraduate-degree requirements; your profile does not verify them")
    score = sum(weight * value for weight, value in parts) / sum(weight for weight, _ in parts)
    return {"job": job, "match_score": round(score, 1), "match_method": "keyword",
            "matching_skills": hits, "match_reasons": reasons}


def _rank_jobs_keyword_based(profile: dict, resume: dict | None, jobs: list, top_n: int) -> list[dict]:
    scored = [item for job in jobs if (item := _profile_match(profile, resume, job))]
    scored.sort(key=lambda item: (-item["match_score"], -(parse_date(item["job"].posted_date).timestamp() if parse_date(item["job"].posted_date) else 0), item["job"].id))
    return scored[:top_n]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        raise ValueError("Embedding dimensions do not match")
    a_arr = np.array(a, dtype=float)
    b_arr = np.array(b, dtype=float)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _embedding_key(text: str) -> str:
    return hashlib.sha256(f"{settings.GEMINI_EMBEDDING_MODEL}:{text}".encode()).hexdigest()


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Batch async requests, with a bounded upstream timeout and validated vectors."""
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")
    model = "models/" + settings.GEMINI_EMBEDDING_MODEL.removeprefix("models/")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/{model}:batchEmbedContents",
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            json={"requests": [
                {"model": model, "content": {"parts": [{"text": text[:8000]}]},
                 "taskType": "SEMANTIC_SIMILARITY"}
                for text in texts
            ]},
        )
        response.raise_for_status()
        items = response.json().get("embeddings", [])
    if len(items) != len(texts):
        raise ValueError("Embedding provider returned an incomplete batch")
    vectors = [item.get("values", []) for item in items]
    if any(not vector or not np.isfinite(np.asarray(vector, dtype=float)).all() for vector in vectors):
        raise ValueError("Embedding provider returned an invalid vector")
    return vectors


async def get_embedding(text: str) -> list[float]:
    return (await get_embeddings([text]))[0]


async def get_user_embedding(user_id: str, profile: dict, resume: dict | None = None) -> list[float]:
    """
    Generate and cache an embedding for a user based on their profile + resume.
    """
    parts: List[str] = []
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
    key = _embedding_key(user_text)
    cached = _user_embeddings.get(user_id)
    if cached and cached[0] == key:
        return cached[1]
    embedding = await get_embedding(user_text)
    if len(_user_embeddings) >= 500:
        _user_embeddings.pop(next(iter(_user_embeddings)))
    _user_embeddings[user_id] = (key, embedding)
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
    # The same bounded candidate set is used in semantic and fallback modes.
    # Every candidate must already match skills/roles and known geography.
    fallback = await asyncio.to_thread(_rank_jobs_keyword_based, profile, resume, jobs, min(top_n, settings.MATCH_CANDIDATE_LIMIT))
    if not settings.GEMINI_API_KEY or not fallback:
        return fallback
    candidates = fallback
    try:
        async with asyncio.timeout(settings.MATCH_TIMEOUT_SECONDS):
            user_emb = await get_user_embedding(user_id, profile, resume)
            missing = []
            for item in candidates:
                job = item["job"]
                text = f"{job.title}\n{job.description[:2000]}"
                cached = _job_embeddings.get(job.id)
                if not cached or cached[0] != _embedding_key(text):
                    missing.append((job, text))
            if missing:
                vectors = await get_embeddings([text for _, text in missing])
                for (job, text), vector in zip(missing, vectors):
                    if len(_job_embeddings) >= 1000:
                        _job_embeddings.pop(next(iter(_job_embeddings)))
                    _job_embeddings[job.id] = (_embedding_key(text), vector)
            scored_jobs = []
            for item in candidates:
                semantic = await compute_match_score(user_emb, _job_embeddings[item["job"].id][1])
                scored_jobs.append({**item, "match_score": round(item["match_score"] * .8 + semantic * .2, 1), "match_method": "semantic"})
            scored_jobs.sort(key=lambda item: (-item["match_score"], item["job"].id))
            return scored_jobs[:top_n]
    except Exception as e:
        logger.warning(
            "Embedding-based ranking failed (%s); falling back to keyword matching",
            e,
        )
        return [{**item, "match_method": "keyword"} for item in fallback]


def clear_user_embedding(user_id: str):
    """Clear cached embedding when profile/resume changes."""
    _user_embeddings.pop(user_id, None)


def clear_job_embeddings():
    """Clear all cached job embeddings (call after job refresh)."""
    _job_embeddings.clear()
