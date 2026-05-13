"""
Gemini client helpers for Week 3 AI features. Prompts live in ai_prompts.py.
"""

import json
import logging
import re
from typing import Any

from app.config import settings
from app.services.ai_prompts import GEMINI_AI_MODEL_ID

logger = logging.getLogger(__name__)

# Truncate long inputs to stay within model context (chars, conservative)
_MAX_RESUME_CHARS = 24_000
_MAX_JOB_CHARS = 16_000


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if len(lines) >= 2 and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _parse_json_object(text: str) -> dict[str, Any]:
    t = _strip_code_fence(text)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", t)
        if m:
            return json.loads(m.group())
        raise


def _require_gemini() -> None:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured on the server")


def _model_name() -> str:
    return getattr(settings, "GEMINI_AI_MODEL", None) or GEMINI_AI_MODEL_ID


async def _generate_text(system_instruction: str, user_content: str) -> str:
    _require_gemini()
    import google.generativeai as genai

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=_model_name(),
        system_instruction=system_instruction,
    )
    response = await model.generate_content_async(user_content)
    if not response or not response.text:
        raise ValueError("Empty response from Gemini")
    return response.text.strip()


async def run_ats_score(resume_text: str, job_description: str) -> dict[str, Any]:
    from app.services.ai_prompts import ATS_SYSTEM, ATS_USER_TEMPLATE

    resume_text = (resume_text or "")[:_MAX_RESUME_CHARS]
    job_description = (job_description or "")[:_MAX_JOB_CHARS]
    user = ATS_USER_TEMPLATE.format(
        resume_text=resume_text,
        job_description=job_description,
    )
    raw = await _generate_text(ATS_SYSTEM, user)
    data = _parse_json_object(raw)
    score = int(data.get("score", 0))
    score = max(0, min(100, score))
    return {
        "score": score,
        "matching_keywords": list(data.get("matching_keywords") or [])[:50],
        "missing_keywords": list(data.get("missing_keywords") or [])[:50],
        "verdict": str(data.get("verdict", "")).strip() or "No verdict returned.",
    }


async def run_cover_letter(
    resume_text: str,
    job_title: str,
    company: str,
    job_description: str,
) -> str:
    from app.services.ai_prompts import COVER_LETTER_SYSTEM, COVER_LETTER_USER_TEMPLATE

    resume_text = (resume_text or "")[:_MAX_RESUME_CHARS]
    job_description = (job_description or "")[:_MAX_JOB_CHARS]
    user = COVER_LETTER_USER_TEMPLATE.format(
        resume_text=resume_text,
        job_title=job_title or "Role",
        company=company or "Company",
        job_description=job_description,
    )
    return await _generate_text(COVER_LETTER_SYSTEM, user)


async def run_skill_gap(user_skills: str, job_required_skills: str) -> dict[str, Any]:
    from app.services.ai_prompts import SKILL_GAP_SYSTEM, SKILL_GAP_USER_TEMPLATE

    user = SKILL_GAP_USER_TEMPLATE.format(
        user_skills=user_skills or "(none listed)",
        job_required_skills=job_required_skills or "(infer from context)",
    )
    raw = await _generate_text(SKILL_GAP_SYSTEM, user)
    data = _parse_json_object(raw)
    courses_raw = data.get("courses") or []
    courses: list[dict[str, Any]] = []
    for c in courses_raw[:12]:
        if not isinstance(c, dict):
            continue
        courses.append(
            {
                "name": str(c.get("name", "")).strip() or "Course",
                "platform": str(c.get("platform", "")).strip() or "Online",
                "url": str(c.get("url", "")).strip() or "https://www.google.com/search?q=course",
                "free": bool(c.get("free", True)),
            }
        )
    return {
        "missing_skills": list(data.get("missing_skills") or [])[:30],
        "courses": courses,
    }


async def run_interview_prep(
    job_title: str,
    job_description: str,
    user_skills: str,
) -> list[dict[str, str]]:
    from app.services.ai_prompts import INTERVIEW_PREP_SYSTEM, INTERVIEW_PREP_USER_TEMPLATE

    job_description = (job_description or "")[:_MAX_JOB_CHARS]
    user = INTERVIEW_PREP_USER_TEMPLATE.format(
        job_title=job_title or "Role",
        job_description=job_description,
        user_skills=user_skills or "(not specified)",
    )
    raw = await _generate_text(INTERVIEW_PREP_SYSTEM, user)
    data = _parse_json_object(raw)
    questions_raw = data.get("questions") or []
    out: list[dict[str, str]] = []
    for q in questions_raw[:5]:
        if not isinstance(q, dict):
            continue
        out.append(
            {
                "question": str(q.get("question", "")).strip(),
                "answer_structure": str(q.get("answer_structure", "")).strip(),
            }
        )
    while len(out) < 5:
        out.append({"question": "", "answer_structure": ""})
    return out[:5]

async def run_resume_improve(resume_text: str, target_role: str) -> list[str]:
    from app.services.ai_prompts import RESUME_IMPROVE_SYSTEM, RESUME_IMPROVE_USER_TEMPLATE

    resume_text = (resume_text or "")[:_MAX_RESUME_CHARS]
    user = RESUME_IMPROVE_USER_TEMPLATE.format(
        resume_text=resume_text,
        target_role=target_role or "Software Engineer / Data Scientist",
    )
    raw = await _generate_text(RESUME_IMPROVE_SYSTEM, user)
    data = _parse_json_object(raw)
    improvements_raw = data.get("improvements") or []
    out: list[str] = []
    for imp in improvements_raw[:5]:
        if isinstance(imp, str):
            out.append(imp.strip())
    return out[:5]
