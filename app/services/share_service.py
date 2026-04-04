"""
Share service — business logic for graph sharing.
"""
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Graph, Share, User
from app.schemas.schemas import ShareCreate, ShareOut


async def _get_graph_or_404(db: AsyncSession, graph_id: uuid.UUID) -> Graph:
    result = await db.execute(select(Graph).where(Graph.id == graph_id))
    graph = result.scalar_one_or_none()
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    return graph


async def _get_share_or_404(db: AsyncSession, share_id: uuid.UUID) -> Share:
    result = await db.execute(select(Share).where(Share.id == share_id))
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    return share


async def create_share(
    db: AsyncSession,
    graph_id: uuid.UUID,
    payload: ShareCreate,
    user_id: str,
) -> ShareOut:
    graph = await _get_graph_or_404(db, graph_id)

    # Only the graph owner can share it
    if str(graph.created_by) != user_id:
        raise HTTPException(status_code=403, detail="Not your graph")

    # Private shares require a target user
    if payload.share_type == "private":
        if not payload.shared_with:
            raise HTTPException(
                status_code=400,
                detail="Private shares require a shared_with user id",
            )
        # Verify target user exists
        result = await db.execute(
            select(User).where(User.id == payload.shared_with)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Target user not found")

        # Prevent sharing with yourself
        if str(payload.shared_with) == user_id:
            raise HTTPException(status_code=400, detail="Cannot share a graph with yourself")

        # Check for duplicate private share
        existing = await db.execute(
            select(Share).where(
                Share.graph_id == graph_id,
                Share.shared_with == payload.shared_with,
                Share.share_type == "private",
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Already shared with this user")

    # Generate a token for link-based shares
    share_token = None
    if payload.share_type == "link":
        share_token = secrets.token_urlsafe(48)

    share = Share(
        graph_id=graph_id,
        shared_by=uuid.UUID(user_id),
        shared_with=payload.shared_with,
        share_type=payload.share_type,
        share_token=share_token,
        expires_at=payload.expires_at,
    )
    db.add(share)
    await db.flush()
    await db.refresh(share)
    return ShareOut.model_validate(share)


async def list_shares(
    db: AsyncSession,
    graph_id: uuid.UUID,
    user_id: str,
) -> list[ShareOut]:
    graph = await _get_graph_or_404(db, graph_id)

    if str(graph.created_by) != user_id:
        raise HTTPException(status_code=403, detail="Not your graph")

    result = await db.execute(
        select(Share).where(Share.graph_id == graph_id)
    )
    shares = result.scalars().all()
    return [ShareOut.model_validate(s) for s in shares]


async def revoke_share(
    db: AsyncSession,
    share_id: uuid.UUID,
    user_id: str,
) -> None:
    share = await _get_share_or_404(db, share_id)

    if str(share.shared_by) != user_id:
        raise HTTPException(status_code=403, detail="Not your share")

    await db.delete(share)


async def resolve_share_token(
    db: AsyncSession,
    token: str,
) -> ShareOut:
    """Resolve a public share link token — returns the share if valid and not expired."""
    result = await db.execute(
        select(Share).where(
            Share.share_token == token,
            Share.share_type == "link",
        )
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found or invalid")

    # Check expiry
    if share.expires_at and share.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Share link has expired")

    return ShareOut.model_validate(share)


async def list_shared_with_me(
    db: AsyncSession,
    user_id: str,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """List graphs shared with the current user (private shares)."""
    query = (
        select(Share)
        .where(
            Share.shared_with == uuid.UUID(user_id),
            Share.share_type == "private",
        )
        .order_by(Share.created_at.desc())
        .limit(limit + 1)
    )

    if cursor:
        cursor_dt = datetime.fromisoformat(cursor)
        query = query.where(Share.created_at < cursor_dt)

    result = await db.execute(query)
    shares = result.scalars().all()

    has_more = len(shares) > limit
    if has_more:
        shares = shares[:limit]

    next_cursor = shares[-1].created_at.isoformat() if has_more and shares else None

    return {
        "items": [ShareOut.model_validate(s) for s in shares],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
