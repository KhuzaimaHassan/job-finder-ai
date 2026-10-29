"""
Gemini client helpers for Week 3 AI features. Prompts live in ai_prompts.py.
"""

import json
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.services.ai_prompts import GEMINI_AI_MODEL_ID, UNTRUSTED_INPUT_RULES
from app.services.learning_resources import for_skills

logger = logging.getLogger(__name__)

# Truncate long inputs to stay within model context (chars, conservative)
_MAX_RESUME_CHARS = 24_000
_MAX_JOB_CHARS = 16_000

_STRING = {"type": "STRING"}
_STRINGS = {"type": "ARRAY", "items": _STRING}


def _object_schema(properties: dict) -> dict:
    return {"type": "OBJECT", "properties": properties, "required": list(properties)}


_ATS_SCHEMA = _object_schema({"score": {"type": "INTEGER"}, "matching_keywords": _STRINGS,
                              "missing_keywords": _STRINGS, "verdict": _STRING})
_GAP_SCHEMA = _object_schema({"missing_skills": _STRINGS})
_INTERVIEW_SCHEMA = _object_schema({"questions": {"type": "ARRAY", "items":
    _object_schema({"question": _STRING, "answer_structure": _STRING})}})
_IMPROVE_SCHEMA = _object_schema({"improvements": _STRINGS})


def _safe_ats_verdict(verdict: str) -> str:
    # Enrollment status is unnecessary for comparing degree levels. Do not
    # publish a model's unverified current-enrollment inference as a fact.
    status = r"(?:ongoing|pursuing|enrolled|current(?:ly)?\s+student)"
    degree = r"(?:bachelor|master|degree|ph\.?d|bsc|msc|bs\b)"
    if re.search(rf"\b{status}\b.{{0,70}}\b{degree}|\b{degree}.{{0,35}}\b{status}\b", verdict, re.I):
        return ("Review the matching and missing requirements below. This AI estimate does not verify "
                "degree completion, employment duration or eligibility; check those against your resume and the posting.")
    return verdict


class AIServiceError(Exception):
    """A provider failure with a safe, actionable client message."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


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
        data = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", t)
        if m:
            data = json.loads(m.group())
        else:
            raise
    if not isinstance(data, dict):
        raise ValueError("AI response must be a JSON object")
    return data


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("AI response must contain lists of strings")
    return [item.strip() for item in value if item.strip()]


def _require_gemini() -> None:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured on the server")


def _model_name() -> str:
    return getattr(settings, "GEMINI_AI_MODEL", None) or GEMINI_AI_MODEL_ID


async def _generate_text(system_instruction: str, user_content: str, *, json_schema: dict | None = None) -> str:
    _require_gemini()
    import google.generativeai as genai
    from google.api_core.exceptions import ResourceExhausted, TooManyRequests, DeadlineExceeded, ServiceUnavailable

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=_model_name(),
        generation_config=({"response_mime_type": "application/json", "response_schema": json_schema}
                           if json_schema is not None else None),
        system_instruction=(system_instruction + "\n" + UNTRUSTED_INPUT_RULES
                            + "\nCurrent date (UTC): " + datetime.now(timezone.utc).date().isoformat()
                            + ". Evaluate career dates relative to this date, not your training cutoff."),
    )
    try:
        async with asyncio.timeout(100):
            response = await model.generate_content_async(user_content)
    except (ResourceExhausted, TooManyRequests) as exc:
        raise AIServiceError(429, "AI provider quota reached. Try again after the quota resets, or ask the site owner to review Gemini limits.") from exc
    except (TimeoutError, DeadlineExceeded) as exc:
        raise AIServiceError(504, "The AI provider took too long. Please try again later.") from exc
    except ServiceUnavailable as exc:
        raise AIServiceError(503, "The AI provider is temporarily unavailable. Please try again later.") from exc
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
    raw = await _generate_text(ATS_SYSTEM, user, json_schema=_ATS_SCHEMA)
    data = _parse_json_object(raw)
    score = int(data.get("score", 0))
    score = max(0, min(100, score))
    return {
        "score": score,
        "matching_keywords": _strings(data.get("matching_keywords", []))[:50],
        "missing_keywords": _strings(data.get("missing_keywords", []))[:50],
        "verdict": _safe_ats_verdict(str(data.get("verdict", "")).strip() or "No verdict returned."),
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


async def run_skill_gap(user_skills: str, job_required_skills: str, job_description: str = "", resume_text: str = "") -> dict[str, Any]:
    from app.services.ai_prompts import SKILL_GAP_SYSTEM, SKILL_GAP_USER_TEMPLATE

    user = SKILL_GAP_USER_TEMPLATE.format(
        user_skills=user_skills or "(none listed)",
        job_required_skills=job_required_skills or "(infer from context)",
        job_description=job_description[:_MAX_JOB_CHARS] or "(not provided)",
        resume_text=resume_text[:_MAX_RESUME_CHARS] or "(not provided)",
    )
    raw = await _generate_text(SKILL_GAP_SYSTEM, user, json_schema=_GAP_SCHEMA)
    data = _parse_json_object(raw)
    raw_missing = data.get("missing_skills") or []
    missing = _strings(raw_missing)[:30]
    return {"missing_skills": missing, "courses": for_skills(missing)}



async def run_interview_prep(
    job_title: str,
    job_description: str,
    user_skills: str,
    resume_text: str = "",
) -> list[dict[str, str]]:
    from app.services.ai_prompts import INTERVIEW_PREP_SYSTEM, INTERVIEW_PREP_USER_TEMPLATE

    job_description = (job_description or "")[:_MAX_JOB_CHARS]
    user = INTERVIEW_PREP_USER_TEMPLATE.format(
        job_title=job_title or "Role",
        job_description=job_description,
        user_skills=user_skills or "(not specified)",
        resume_text=resume_text[:_MAX_RESUME_CHARS] or "(not provided)",
    )
    raw = await _generate_text(INTERVIEW_PREP_SYSTEM, user, json_schema=_INTERVIEW_SCHEMA)
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
    out = [q for q in out if q["question"] and q["answer_structure"]]
    if not out:
        raise ValueError("No usable interview questions returned")
    return out[:5]

async def run_resume_improve(resume_text: str, target_role: str) -> list[str]:
    from app.services.ai_prompts import RESUME_IMPROVE_SYSTEM, RESUME_IMPROVE_USER_TEMPLATE

    resume_text = (resume_text or "")[:_MAX_RESUME_CHARS]
    user = RESUME_IMPROVE_USER_TEMPLATE.format(
        resume_text=resume_text,
        target_role=target_role or "Software Engineer / Data Scientist",
    )
    raw = await _generate_text(RESUME_IMPROVE_SYSTEM, user, json_schema=_IMPROVE_SCHEMA)
    data = _parse_json_object(raw)
    improvements_raw = data.get("improvements") or []
    out: list[str] = []
    for imp in improvements_raw[:5]:
        if isinstance(imp, str) and imp.strip():
            out.append(imp.strip())
    if not out:
        raise ValueError("No usable resume improvements returned")
    return out[:5]
