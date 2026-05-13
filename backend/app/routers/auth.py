"""
Auth Router
-----------
Authentication endpoints.
"""

from fastapi import APIRouter, Depends
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Return the current authenticated user."""
    return user
