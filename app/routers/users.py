"""
Users router — /api/v1/users
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.schemas.schemas import FollowOut, UserProfile, UserProfileWithStats
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfileWithStats)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get the current user's profile with follower/following counts."""
    return await user_service.get_me(db, user_id)


@router.get("/{username}", response_model=UserProfileWithStats)
async def get_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Get a user's public profile with follower/following counts."""
    return await user_service.get_profile(db, username, user_id)


@router.get("/{username}/followers", response_model=list[UserProfile])
async def list_followers(
    username: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """List users who follow the given user."""
    return await user_service.list_followers(db, username)


@router.get("/{username}/following", response_model=list[UserProfile])
async def list_following(
    username: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """List users the given user follows."""
    return await user_service.list_following(db, username)


@router.post("/{user_id}/follow", response_model=FollowOut, status_code=201)
async def follow_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    requesting_user_id: str = Depends(get_current_user_id),
):
    """Follow a user."""
    return await user_service.follow_user(db, user_id, requesting_user_id)


@router.delete("/{user_id}/follow", status_code=204)
async def unfollow_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    requesting_user_id: str = Depends(get_current_user_id),
):
    """Unfollow a user."""
    await user_service.unfollow_user(db, user_id, requesting_user_id)
