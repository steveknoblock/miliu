"""
Graphs router — /api/v1/graphs
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.schemas.schemas import (
    EdgeCreate,
    EdgeOut,
    GraphCreate,
    GraphDetail,
    GraphOut,
    GraphShift,
    GraphUpdate,
)
from app.services import graph_service

router = APIRouter(prefix="/graphs", tags=["graphs"])


@router.post("", response_model=GraphDetail, status_code=201)
async def create_graph(
    payload: GraphCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Create a new graph with a designated key node."""
    return await graph_service.create_graph(db, payload, user_id)


@router.get("", response_model=dict)
async def list_my_graphs(
    cursor: Optional[str] = Query(None, description="ISO timestamp cursor for pagination"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """List the current user's graphs, newest first, cursor-paginated."""
    return await graph_service.list_user_graphs(db, user_id, cursor=cursor, limit=limit)


@router.get("/{graph_id}", response_model=GraphDetail)
async def get_graph(
    graph_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Retrieve a full graph with all nodes and edges."""
    return await graph_service.get_graph(db, graph_id, user_id)


@router.patch("/{graph_id}", response_model=GraphDetail)
async def update_graph(
    graph_id: uuid.UUID,
    payload: GraphUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Update a graph's title or description."""
    return await graph_service.update_graph(db, graph_id, payload, user_id)


@router.delete("/{graph_id}", status_code=204)
async def delete_graph(
    graph_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Delete a graph (and its edges via cascade)."""
    await graph_service.delete_graph(db, graph_id, user_id)


# ── Edge management ───────────────────────────────────────────────────────────

@router.post("/{graph_id}/edges", response_model=GraphDetail, status_code=201)
async def add_edge(
    graph_id: uuid.UUID,
    payload: EdgeCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Add a context node to a graph via a new edge.
    Maximum 4 context nodes (5 nodes total) enforced.
    """
    return await graph_service.add_edge(db, graph_id, payload, user_id)


@router.delete("/{graph_id}/edges/{edge_id}", response_model=GraphDetail)
async def remove_edge(
    graph_id: uuid.UUID,
    edge_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Remove a context node from a graph by deleting its edge."""
    return await graph_service.remove_edge(db, graph_id, edge_id, user_id)


# ── Shift (fork) ──────────────────────────────────────────────────────────────

@router.post("/{graph_id}/shift", response_model=GraphDetail, status_code=201)
async def shift_graph(
    graph_id: uuid.UUID,
    payload: GraphShift,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Fork a graph into a new one.
    - shift_type='with_context': copies all existing context edges.
    - shift_type='fresh': new graph starts with only the key node.
    """
    return await graph_service.shift_graph(db, graph_id, payload, user_id)
