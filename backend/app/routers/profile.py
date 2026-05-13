"""
Profile Router
--------------
User profile CRUD endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.services.auth import get_current_user
from app.services.supabase_client import get_supabase
from app.services.embeddings import clear_user_embedding

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_years: Optional[int] = None
    target_roles: Optional[List[str]] = None
    location: Optional[str] = None


@router.get("")
async def get_profile(user: dict = Depends(get_current_user)):
    """Get the current user's profile."""
    supabase = get_supabase()
    result = supabase.table("profiles").select("*").eq("user_id", user["id"]).execute()

    if result.data:
        return result.data[0]

    # Auto-create profile if it doesn't exist
    new_profile = {
        "user_id": user["id"],
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "skills": [],
        "experience_years": 0,
        "target_roles": [],
        "location": "",
    }
    supabase.table("profiles").insert(new_profile).execute()
    return new_profile


@router.patch("")
async def update_profile(
    updates: ProfileUpdate,
    user: dict = Depends(get_current_user),
):
    """Update the current user's profile."""
    supabase = get_supabase()

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = (
        supabase.table("profiles")
        .update(update_data)
        .eq("user_id", user["id"])
        .execute()
    )

    # Clear cached embedding so it regenerates with new profile
    clear_user_embedding(user["id"])

    if result.data:
        return result.data[0]

    raise HTTPException(status_code=404, detail="Profile not found")


@router.post("/sync-from-resume")
async def sync_from_resume(user: dict = Depends(get_current_user)):
    """Populate profile skills and info from the latest parsed resume."""
    supabase = get_supabase()

    # Get latest resume
    resume_result = (
        supabase.table("resumes")
        .select("*")
        .eq("user_id", user["id"])
        .order("parsed_at", desc=True)
        .limit(1)
        .execute()
    )

    if not resume_result.data:
        raise HTTPException(status_code=404, detail="No parsed resume found")

    resume = resume_result.data[0]

    # Extract data for profile
    update_data = {}
    if resume.get("skills"):
        update_data["skills"] = resume["skills"]

    # Try to guess experience years from experience entries
    exp = resume.get("experience", [])
    if isinstance(exp, list) and len(exp) > 0:
        update_data["experience_years"] = len(exp)

    # Extract role titles as target roles
    if isinstance(exp, list):
        roles = [e.get("title", "") for e in exp if isinstance(e, dict) and e.get("title")]
        if roles:
            update_data["target_roles"] = roles[:5]

    if update_data:
        supabase.table("profiles").update(update_data).eq("user_id", user["id"]).execute()
        clear_user_embedding(user["id"])

    # Return updated profile
    result = supabase.table("profiles").select("*").eq("user_id", user["id"]).execute()
    return result.data[0] if result.data else {}
