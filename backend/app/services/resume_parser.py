"""
Resume Parser Service
---------------------
Extracts text from PDF using pdfplumber, then uses Gemini to structure it.
"""

import io
import json
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file using pdfplumber."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        # Fallback to PyPDF2
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n\n".join(text_parts)
        except Exception as e2:
            logger.error(f"PyPDF2 fallback also failed: {e2}")
            raise ValueError("Could not extract text from PDF")


async def parse_resume_with_gemini(raw_text: str) -> dict:
    """
    Use Gemini 2.5 Flash to extract structured data from resume text.
    Returns: {skills: [], education: [], experience: [], projects: []}
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")

    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)

    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""Analyze this resume and extract structured data. Return ONLY valid JSON with no markdown formatting.

The JSON must have exactly these keys:
- "skills": array of strings (technical skills like "Python", "Machine Learning", etc.)
- "education": array of objects with "degree", "institution", "year" fields
- "experience": array of objects with "title", "company", "duration", "description" fields
- "projects": array of objects with "name", "description", "technologies" fields
- "summary": a 2-3 sentence professional summary

Resume text:
---
{raw_text[:8000]}
---

Return ONLY the JSON object, no markdown code blocks, no explanation."""

    try:
        response = await model.generate_content_async(prompt)
        response_text = response.text.strip()

        # Clean markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            response_text = response_text.strip()

        parsed = json.loads(response_text)

        # Ensure all expected keys exist
        result = {
            "skills": parsed.get("skills", []),
            "education": parsed.get("education", []),
            "experience": parsed.get("experience", []),
            "projects": parsed.get("projects", []),
            "summary": parsed.get("summary", ""),
        }
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON: {e}")
        logger.error(f"Response was: {response_text[:500]}")
        raise ValueError("Failed to parse Gemini response as JSON")
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise ValueError(f"Gemini API error: {str(e)}")
