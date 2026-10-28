import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.services.auth import get_current_user
from app.services.supabase_client import get_user_supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/applications", tags=["applications"])
Status = Literal["Saved", "Applied", "Interview", "Offer", "Rejected"]


class ApplicationCreate(BaseModel):
    job_id: str = Field(min_length=1, max_length=2000)
    job_title: str = Field(min_length=1, max_length=500)
    company: str = Field(min_length=1, max_length=500)
    status: Status = "Saved"
    notes: str = Field("", max_length=6000)


class ApplicationUpdate(BaseModel):
    status: Status | None = None
    notes: str | None = Field(None, max_length=6000)


@router.get("")
def list_applications(user: dict = Depends(get_current_user)):
    try:
        return get_user_supabase(user["token"]).table("applications").select("*").eq(
            "user_id", user["id"]).order("updated_at", desc=True).execute().data
    except Exception:
        logger.exception("Could not load applications")
        raise HTTPException(503, "Could not load applications. Please try again.")


@router.post("")
def create_application(body: ApplicationCreate, user: dict = Depends(get_current_user)):
    db = get_user_supabase(user["token"])
    def existing():
        result = db.table("applications").select("*").eq("user_id", user["id"]).eq("job_id", body.job_id).execute()
        return result.data[0] if result.data else None
    try:
        found = existing()
        if found:
            return found
        now = datetime.now(timezone.utc).isoformat()
        data = {**body.model_dump(), "user_id": user["id"], "updated_at": now,
                "applied_date": now if body.status != "Saved" else None,
                # Existing PK enforces concurrent idempotency without a schema migration.
                "id": str(uuid5(NAMESPACE_URL, f"job-finder:{user['id']}:{body.job_id}"))}
        try:
            result = db.table("applications").insert(data).execute()
        except Exception as exc:
            if getattr(exc, "code", None) == "23505":
                found = existing()
                if found:
                    return found
            raise
        if result.data:
            return result.data[0]
        raise HTTPException(503, "Could not save this application. Please try again.")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Could not create application")
        raise HTTPException(503, "Could not save this application. Please try again.")


@router.patch("/{app_id}")
def update_application(app_id: str, body: ApplicationUpdate, user: dict = Depends(get_current_user)):
    db = get_user_supabase(user["token"])
    try:
        existing = db.table("applications").select("*").eq("id", app_id).eq("user_id", user["id"]).execute().data
        if not existing:
            raise HTTPException(404, "Application not found")
        changes = body.model_dump(exclude_none=True)
        if not changes:
            return existing[0]
        changes["updated_at"] = datetime.now(timezone.utc).isoformat()
        if body.status == "Applied" and (not existing[0].get("applied_date") or existing[0]["status"] == "Saved"):
            changes["applied_date"] = changes["updated_at"]
        db.table("applications").update(changes).eq("id", app_id).eq("user_id", user["id"]).execute()
        result = db.table("applications").select("*").eq("id", app_id).eq("user_id", user["id"]).execute()
        if result.data:
            return result.data[0]
        raise HTTPException(404, "Application not found")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Could not update application")
        raise HTTPException(503, "Could not save your changes. Please try again.")


@router.delete("/{app_id}")
def delete_application(app_id: str, user: dict = Depends(get_current_user)):
    db = get_user_supabase(user["token"])
    try:
        found = db.table("applications").select("id").eq("id", app_id).eq("user_id", user["id"]).execute()
        if not found.data:
            raise HTTPException(404, "Application not found")
        db.table("applications").delete().eq("id", app_id).eq("user_id", user["id"]).execute()
        return {"success": True}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Could not delete application")
        raise HTTPException(503, "Could not remove this application. Please try again.")
