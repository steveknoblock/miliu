"""
Feed router — GET /api/v1/feed
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.schemas.schemas import FeedResponse
from app.services import feed_service

router = APIRouter(tags=["feed"])


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    cursor: Optional[str] = Query(None, description="Opaque pagination cursor"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns a personalised chronological feed of public graphs.

    Blends two pools:
    - Graphs from users you follow
    - Discovery graphs from users you don't follow (1 per 3 followed items)

    Use next_cursor from the response to fetch the next page.
    Returns an empty items array (not 404) when no content is available.
    """
    return await feed_service.get_feed(db, user_id, cursor=cursor, limit=limit)
