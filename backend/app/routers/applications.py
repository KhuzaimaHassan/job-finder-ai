from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.auth import get_current_user
from supabase import Client
from app.services.supabase_client import get_supabase

router = APIRouter(prefix="/api/applications", tags=["applications"])

class ApplicationCreate(BaseModel):
    job_id: str
    job_title: str
    company: str
    status: Literal["Saved", "Applied", "Interview", "Offer", "Rejected"] = "Saved"
    notes: Optional[str] = ""

class ApplicationUpdate(BaseModel):
    status: Optional[Literal["Saved", "Applied", "Interview", "Offer", "Rejected"]] = None
    notes: Optional[str] = None

@router.get("")
def list_applications(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    supabase: Client = get_supabase()
    res = supabase.table("applications").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
    return res.data

@router.post("")
def create_application(body: ApplicationCreate, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    supabase: Client = get_supabase()
    
    # Check if already exists
    existing = supabase.table("applications").select("*").eq("user_id", user_id).eq("job_id", body.job_id).execute()
    if existing.data:
        return existing.data[0]
        
    data = {
        "user_id": user_id,
        "job_id": body.job_id,
        "job_title": body.job_title,
        "company": body.company,
        "status": body.status,
        "notes": body.notes
    }
    res = supabase.table("applications").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create application")
    return res.data[0]

@router.patch("/{app_id}")
def update_application(app_id: str, body: ApplicationUpdate, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    supabase: Client = get_supabase()
    
    # Ensure ownership
    existing = supabase.table("applications").select("*").eq("id", app_id).eq("user_id", user_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Application not found")
        
    update_data = {}
    if body.status is not None:
        update_data["status"] = body.status
    if body.notes is not None:
        update_data["notes"] = body.notes
        
    if not update_data:
        return existing.data[0]
        
    # Set updated_at via database or manually
    res = supabase.table("applications").update(update_data).eq("id", app_id).execute()
    return res.data[0]

@router.delete("/{app_id}")
def delete_application(app_id: str, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    supabase: Client = get_supabase()
    
    existing = supabase.table("applications").select("*").eq("id", app_id).eq("user_id", user_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Application not found")
        
    supabase.table("applications").delete().eq("id", app_id).execute()
    return {"success": True}
