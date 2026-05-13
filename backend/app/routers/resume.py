"""
Resume Router
-------------
Resume upload, parsing, and retrieval endpoints.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.services.auth import get_current_user
from app.services.supabase_client import get_supabase
from app.services.resume_parser import extract_text_from_pdf, parse_resume_with_gemini
from app.services.embeddings import clear_user_embedding

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/upload")
async def upload_and_parse_resume(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """
    Upload a PDF resume, extract text, parse with Gemini, and store results.
    Combines upload + parse into one step for simplicity.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Read file
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    logger.info(f"Processing resume for user {user['id']}: {file.filename}")

    # Step 1: Extract text
    try:
        raw_text = extract_text_from_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not raw_text or len(raw_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Could not extract enough text from PDF. Try a different file.",
        )

    logger.info(f"Extracted {len(raw_text)} chars from resume")

    # Step 2: Parse with Gemini
    try:
        parsed = await parse_resume_with_gemini(raw_text)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    logger.info(f"Gemini parsed: {len(parsed.get('skills', []))} skills found")

    # Step 3: Store in Supabase
    supabase = get_supabase()

    # Upload PDF to Supabase Storage
    file_path = f"{user['id']}/{file.filename}"
    try:
        supabase.storage.from_("resumes").upload(
            file_path,
            file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
    except Exception as e:
        logger.warning(f"Storage upload failed (non-critical): {e}")
        file_path = ""

    # Delete old resumes for this user, then insert new
    try:
        supabase.table("resumes").delete().eq("user_id", user["id"]).execute()
    except Exception:
        pass

    resume_record = {
        "user_id": user["id"],
        "raw_text": raw_text[:50000],  # Limit storage
        "skills": parsed.get("skills", []),
        "education": parsed.get("education", []),
        "experience": parsed.get("experience", []),
        "projects": parsed.get("projects", []),
        "file_path": file_path,
        "parsed_at": datetime.utcnow().isoformat(),
    }

    result = supabase.table("resumes").insert(resume_record).execute()

    # Clear cached embedding so it regenerates with new resume
    clear_user_embedding(user["id"])

    return {
        "message": "Resume parsed successfully",
        "skills": parsed.get("skills", []),
        "education": parsed.get("education", []),
        "experience": parsed.get("experience", []),
        "projects": parsed.get("projects", []),
        "summary": parsed.get("summary", ""),
    }


@router.get("")
async def get_resume(user: dict = Depends(get_current_user)):
    """Get the latest parsed resume for the current user."""
    supabase = get_supabase()
    result = (
        supabase.table("resumes")
        .select("*")
        .eq("user_id", user["id"])
        .order("parsed_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return {"parsed": False}

    resume = result.data[0]
    raw_text = resume.get("raw_text") or ""
    return {
        "parsed": True,
        "skills": resume.get("skills", []),
        "education": resume.get("education", []),
        "experience": resume.get("experience", []),
        "projects": resume.get("projects", []),
        "parsed_at": resume.get("parsed_at"),
        "raw_text": raw_text[:60000] if isinstance(raw_text, str) else "",
    }
