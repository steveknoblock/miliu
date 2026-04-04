"""
Shares router — /api/v1/graphs/{id}/shares and /api/v1/shares
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.schemas.schemas import ShareCreate, ShareOut
from app.services import share_service

router = APIRouter(tags=["shares"])


# ── Shares scoped to a graph ──────────────────────────────────────────────────

@router.post("/graphs/{graph_id}/shares", response_model=ShareOut, status_code=201)
async def create_share(
    graph_id: uuid.UUID,
    payload: ShareCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Share a graph with another user or generate a link.
    - share_type='private': share with a specific user (shared_with required)
    - share_type='link': generate a shareable token link
    - share_type='public': make the graph publicly accessible
    """
    return await share_service.create_share(db, graph_id, payload, user_id)


@router.get("/graphs/{graph_id}/shares", response_model=list[ShareOut])
async def list_shares(
    graph_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """List all shares for a graph (owner only)."""
    return await share_service.list_shares(db, graph_id, user_id)


# ── Share management ──────────────────────────────────────────────────────────

@router.delete("/shares/{share_id}", status_code=204)
async def revoke_share(
    share_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Revoke a share."""
    await share_service.revoke_share(db, share_id, user_id)


# ── Public token resolution (no auth required) ────────────────────────────────

@router.get("/shares/token/{token}", response_model=ShareOut)
async def resolve_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Resolve a share link token. No authentication required.
    Returns the share details if the token is valid and not expired.
    """
    return await share_service.resolve_share_token(db, token)


# ── Graphs shared with me ─────────────────────────────────────────────────────

@router.get("/shares/me", response_model=dict)
async def shared_with_me(
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """List graphs that have been privately shared with the current user."""
    return await share_service.list_shared_with_me(db, user_id, cursor=cursor, limit=limit)
