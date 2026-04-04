"""
Nodes router — /api/v1/nodes
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.models import Node
from app.schemas.schemas import NodeCreate, NodeOut, NodeUpdate

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.post("", response_model=NodeOut, status_code=201)
async def create_node(
    payload: NodeCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    node = Node(
        title=payload.title,
        content=payload.content,
        node_type=payload.node_type,
        metadata_=payload.metadata,
        created_by=uuid.UUID(user_id),
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return node


@router.get("/{node_id}", response_model=NodeOut)
async def get_node(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(Node).where(Node.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.patch("/{node_id}", response_model=NodeOut)
async def update_node(
    node_id: uuid.UUID,
    payload: NodeUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(Node).where(Node.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if str(node.created_by) != user_id:
        raise HTTPException(status_code=403, detail="Not your node")

    if payload.title is not None:
        node.title = payload.title
    if payload.content is not None:
        node.content = payload.content
    if payload.metadata is not None:
        node.metadata_ = payload.metadata

    await db.flush()
    await db.refresh(node)
    return node


@router.delete("/{node_id}", status_code=204)
async def delete_node(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(Node).where(Node.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if str(node.created_by) != user_id:
        raise HTTPException(status_code=403, detail="Not your node")
    await db.delete(node)
