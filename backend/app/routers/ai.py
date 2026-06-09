"""
Week 3 — Gemini-powered AI endpoints (ATS, cover letter, skill gap, interview prep).
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from app.services.auth import get_current_user
from app.services import ai_gemini

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])


# --- Request / response models ---


class ATSScoreRequest(BaseModel):
    resume_text: str = Field(..., min_length=10)
    job_description: str = Field(..., min_length=10)


class ATSScoreResponse(BaseModel):
    score: int
    matching_keywords: List[str]
    missing_keywords: List[str]
    verdict: str


class CoverLetterRequest(BaseModel):
    resume_text: str = Field(..., min_length=10)
    job_title: str = ""
    company: str = ""
    job_description: str = Field(..., min_length=10)


class CoverLetterResponse(BaseModel):
    cover_letter: str


class SkillGapRequest(BaseModel):
    user_skills: str = ""
    job_required_skills: str = Field(..., min_length=3)


class CourseSuggestion(BaseModel):
    name: str
    platform: str
    url: str
    free: bool = True


class SkillGapResponse(BaseModel):
    missing_skills: List[str]
    courses: List[CourseSuggestion]


class InterviewPrepRequest(BaseModel):
    job_title: str = ""
    job_description: str = Field(..., min_length=10)
    user_skills: str = ""


class InterviewQuestionItem(BaseModel):
    question: str
    answer_structure: str


class InterviewPrepResponse(BaseModel):
    questions: List[InterviewQuestionItem]


def _gemini_http(exc: Exception) -> HTTPException:
    msg = str(exc)
    if "GEMINI_API_KEY" in msg or "not configured" in msg.lower():
        return HTTPException(
            status_code=503,
            detail="AI features require GEMINI_API_KEY on the server.",
        )
    return HTTPException(status_code=500, detail="AI request failed")


@router.post("/ats-score", response_model=ATSScoreResponse)
@limiter.limit("10/minute")
async def ats_score(
    request: Request,
    body: ATSScoreRequest,
    _user: dict = Depends(get_current_user),
):
    try:
        result = await ai_gemini.run_ats_score(
            body.resume_text,
            body.job_description,
        )
        return ATSScoreResponse(**result)
    except ValueError as e:
        raise _gemini_http(e) from e
    except Exception as e:
        logger.error(f"ATS score failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while calculating ATS score") from e


@router.post("/cover-letter", response_model=CoverLetterResponse)
@limiter.limit("10/minute")
async def cover_letter(
    request: Request,
    body: CoverLetterRequest,
    _user: dict = Depends(get_current_user),
):
    try:
        text = await ai_gemini.run_cover_letter(
            body.resume_text,
            body.job_title,
            body.company,
            body.job_description,
        )
        return CoverLetterResponse(cover_letter=text)
    except ValueError as e:
        raise _gemini_http(e) from e
    except Exception as e:
        logger.error(f"Cover letter failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while generating cover letter") from e


@router.post("/skill-gap", response_model=SkillGapResponse)
@limiter.limit("10/minute")
async def skill_gap(
    request: Request,
    body: SkillGapRequest,
    _user: dict = Depends(get_current_user),
):
    try:
        result = await ai_gemini.run_skill_gap(
            body.user_skills,
            body.job_required_skills,
        )
        courses = [CourseSuggestion(**c) for c in result["courses"]]
        return SkillGapResponse(
            missing_skills=result["missing_skills"],
            courses=courses,
        )
    except ValueError as e:
        raise _gemini_http(e) from e
    except Exception as e:
        logger.error(f"Skill gap failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while calculating skill gap") from e


@router.post("/interview-prep", response_model=InterviewPrepResponse)
@limiter.limit("10/minute")
async def interview_prep(
    request: Request,
    body: InterviewPrepRequest,
    _user: dict = Depends(get_current_user),
):
    try:
        items = await ai_gemini.run_interview_prep(
            body.job_title,
            body.job_description,
            body.user_skills,
        )
        questions = [
            InterviewQuestionItem(question=q["question"], answer_structure=q["answer_structure"])
            for q in items
        ]
        return InterviewPrepResponse(questions=questions)
    except ValueError as e:
        raise _gemini_http(e) from e
    except Exception as e:
        logger.error(f"Interview prep failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while generating interview prep") from e

class ResumeImproveRequest(BaseModel):
    resume_text: str = Field(..., min_length=10)
    target_role: str = ""

class ResumeImproveResponse(BaseModel):
    improvements: List[str]

@router.post("/resume-improve", response_model=ResumeImproveResponse)
@limiter.limit("10/minute")
async def resume_improve(
    request: Request,
    body: ResumeImproveRequest,
    _user: dict = Depends(get_current_user),
):
    try:
        items = await ai_gemini.run_resume_improve(
            body.resume_text,
            body.target_role,
        )
        return ResumeImproveResponse(improvements=items)
    except ValueError as e:
        raise _gemini_http(e) from e
    except Exception as e:
        logger.error(f"Resume improve failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while generating resume improvements") from e
