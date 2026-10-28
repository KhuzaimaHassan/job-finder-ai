"""
Profile Router
--------------
User profile CRUD endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from app.services.auth import get_current_user
from app.services.supabase_client import get_supabase, get_user_supabase
from app.services.embeddings import clear_user_embedding

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    skills: Optional[List[str]] = None
    experience_years: Optional[int] = Field(None, ge=0, le=50)
    target_roles: Optional[List[str]] = None
    location: Optional[str] = None


@router.get("")
def get_profile(user: dict = Depends(get_current_user)):
    """Get the current user's profile."""
    supabase = get_user_supabase(user["token"])
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
def update_profile(
    updates: ProfileUpdate,
    user: dict = Depends(get_current_user),
):
    """Update the current user's profile."""
    supabase = get_user_supabase(user["token"])

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = (
        supabase.table("profiles")
        .update(update_data)
        .eq("user_id", user["id"])
        .execute()
    )

    # Clear cached embedding so it regenerates with new profile
    clear_user_embedding(user["id"])

    # PostgREST might return empty data if no values were actually changed.
    # To be safe, we just fetch and return the updated profile.
    final_result = supabase.table("profiles").select("*").eq("user_id", user["id"]).execute()
    if final_result.data:
        return final_result.data[0]

    raise HTTPException(status_code=404, detail="Profile not found")


@router.post("/sync-from-resume")
def sync_from_resume(user: dict = Depends(get_current_user)):
    """Populate profile skills and info from the latest parsed resume."""
    supabase = get_user_supabase(user["token"])

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
    current = supabase.table("profiles").select("*").eq("user_id", user["id"]).execute().data
    if resume.get("skills"):
        existing_skills = current[0].get("skills", []) if current else []
        update_data["skills"] = list(dict.fromkeys([*existing_skills, *resume["skills"]]))
    # Experience and target roles are user decisions. Job count is not tenure,
    # and past titles must not overwrite the user's desired future roles.

    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        supabase.table("profiles").update(update_data).eq("user_id", user["id"]).execute()
        clear_user_embedding(user["id"])

    # Return updated profile
    result = supabase.table("profiles").select("*").eq("user_id", user["id"]).execute()
    return result.data[0] if result.data else {}
