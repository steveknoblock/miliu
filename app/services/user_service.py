"""
User service — profiles, follow, unfollow.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Follow, User
from app.schemas.schemas import FollowOut, UserProfile, UserProfileWithStats


async def _get_user_by_username_or_404(db: AsyncSession, username: str) -> User:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _get_user_by_id_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def get_profile(
    db: AsyncSession,
    username: str,
    requesting_user_id: str,
) -> UserProfileWithStats:
    user = await _get_user_by_username_or_404(db, username)

    # Follower count
    follower_count_result = await db.execute(
        select(func.count()).where(Follow.following_id == user.id)
    )
    follower_count = follower_count_result.scalar() or 0

    # Following count
    following_count_result = await db.execute(
        select(func.count()).where(Follow.follower_id == user.id)
    )
    following_count = following_count_result.scalar() or 0

    # Is the requesting user following this profile?
    is_following_result = await db.execute(
        select(Follow).where(
            Follow.follower_id == uuid.UUID(requesting_user_id),
            Follow.following_id == user.id,
        )
    )
    is_following = is_following_result.scalar_one_or_none() is not None

    return UserProfileWithStats(
        id=user.id,
        username=user.username,
        created_at=user.created_at,
        follower_count=follower_count,
        following_count=following_count,
        is_following=is_following,
    )


async def get_me(db: AsyncSession, user_id: str) -> UserProfileWithStats:
    return await get_profile(db, await _get_username(db, user_id), user_id)


async def _get_username(db: AsyncSession, user_id: str) -> str:
    result = await db.execute(select(User.username).where(User.id == uuid.UUID(user_id)))
    return result.scalar_one()


async def follow_user(
    db: AsyncSession,
    target_user_id: uuid.UUID,
    requesting_user_id: str,
) -> FollowOut:
    requester_uuid = uuid.UUID(requesting_user_id)

    # Can't follow yourself
    if target_user_id == requester_uuid:
        raise HTTPException(status_code=400, detail="You cannot follow yourself")

    # Target must exist
    await _get_user_by_id_or_404(db, target_user_id)

    # Check if already following
    existing = await db.execute(
        select(Follow).where(
            Follow.follower_id == requester_uuid,
            Follow.following_id == target_user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already following this user")

    follow = Follow(follower_id=requester_uuid, following_id=target_user_id)
    db.add(follow)
    await db.flush()
    await db.refresh(follow)
    return FollowOut.model_validate(follow)


async def unfollow_user(
    db: AsyncSession,
    target_user_id: uuid.UUID,
    requesting_user_id: str,
) -> None:
    requester_uuid = uuid.UUID(requesting_user_id)

    result = await db.execute(
        select(Follow).where(
            Follow.follower_id == requester_uuid,
            Follow.following_id == target_user_id,
        )
    )
    follow = result.scalar_one_or_none()
    if not follow:
        raise HTTPException(status_code=404, detail="You are not following this user")

    await db.delete(follow)


async def list_followers(
    db: AsyncSession,
    username: str,
) -> list[UserProfile]:
    user = await _get_user_by_username_or_404(db, username)

    result = await db.execute(
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.following_id == user.id)
        .order_by(Follow.created_at.desc())
    )
    return [UserProfile.model_validate(u) for u in result.scalars().all()]


async def list_following(
    db: AsyncSession,
    username: str,
) -> list[UserProfile]:
    user = await _get_user_by_username_or_404(db, username)

    result = await db.execute(
        select(User)
        .join(Follow, Follow.following_id == User.id)
        .where(Follow.follower_id == user.id)
        .order_by(Follow.created_at.desc())
    )
    return [UserProfile.model_validate(u) for u in result.scalars().all()]
