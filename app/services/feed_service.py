"""
Feed service — GET /api/v1/feed

Merges two content pools into a single chronological stream:
  Pool 1: public graphs from users the requester follows
  Pool 2: discovery — recent public graphs from non-followed users

Interleaving ratio: 1 discovery per 3 followed items.
Ordering: created_at DESC throughout.
Pagination: cursor encodes (created_at, id) as base64 JSON.
"""
import base64
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, exists, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Edge, Follow, Graph, Node, Share, User
from app.schemas.schemas import (
    FeedAuthor,
    FeedContextNode,
    FeedItemOut,
    FeedKeyNode,
    FeedParent,
    FeedResponse,
)

# ── Cursor helpers ────────────────────────────────────────────────────────────

def _encode_cursor(created_at: datetime, graph_id: uuid.UUID) -> str:
    payload = {"t": created_at.isoformat(), "id": str(graph_id)}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = json.loads(base64.b64decode(cursor).decode())
        return datetime.fromisoformat(payload["t"]), uuid.UUID(payload["id"])
    except Exception:
        raise ValueError("Invalid cursor")


# ── Markdown stripper ─────────────────────────────────────────────────────────

def _strip_markdown(text: str, max_length: int = 200) -> str:
    """Remove common markdown syntax and truncate to max_length."""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    # Remove headings, bold, italic, links, images
    text = re.sub(r"#{1,6}\s+", "", text)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


# ── Public share check ────────────────────────────────────────────────────────

def _is_public_subquery(graph_id_col):
    """Returns a subquery expression: True if graph has an active public share."""
    return exists(
        select(Share.id).where(
            Share.graph_id == graph_id_col,
            Share.share_type == "public",
        )
    )


# ── Graph → FeedItemOut builder ───────────────────────────────────────────────

async def _build_feed_item(
    db: AsyncSession,
    graph: Graph,
    is_discovery: bool,
) -> FeedItemOut:
    # Author
    author_result = await db.execute(select(User).where(User.id == graph.created_by))
    author = author_result.scalar_one()

    # Key node
    key_node_result = await db.execute(select(Node).where(Node.id == graph.key_node_id))
    key_node = key_node_result.scalar_one()

    # Context nodes (titles only, via edges)
    edges_result = await db.execute(
        select(Edge).where(Edge.graph_id == graph.id)
    )
    edges = edges_result.scalars().all()
    context_node_ids = [e.source_node_id for e in edges]

    context_nodes = []
    if context_node_ids:
        ctx_result = await db.execute(
            select(Node).where(Node.id.in_(context_node_ids))
        )
        context_nodes = [
            FeedContextNode(id=n.id, title=n.title)
            for n in ctx_result.scalars().all()
        ]

    # Is public?
    is_public_result = await db.execute(
        select(exists(
            select(Share.id).where(
                Share.graph_id == graph.id,
                Share.share_type == "public",
            )
        ))
    )
    is_public = is_public_result.scalar()

    # Parent (if this is a shift)
    parent = None
    if graph.shift_type and graph.parent_graph_id:
        parent_graph_result = await db.execute(
            select(Graph).where(Graph.id == graph.parent_graph_id)
        )
        parent_graph = parent_graph_result.scalar_one_or_none()
        if parent_graph:
            parent_author_result = await db.execute(
                select(User).where(User.id == parent_graph.created_by)
            )
            parent_author = parent_author_result.scalar_one_or_none()
            parent = FeedParent(
                id=parent_graph.id,
                title=parent_graph.title,
                author_username=parent_author.username if parent_author else "unknown",
            )

    # Resolve title: graph title or fall back to key node title
    title = graph.title or key_node.title

    return FeedItemOut(
        id=graph.id,
        title=title,
        created_at=graph.created_at,
        is_public=is_public,
        is_discovery=is_discovery,
        shift_type=graph.shift_type,
        author=FeedAuthor(id=author.id, username=author.username),
        key_node=FeedKeyNode(
            id=key_node.id,
            title=key_node.title,
            content_preview=_strip_markdown(key_node.content),
        ),
        context_nodes=context_nodes,
        parent=parent,
    )


# ── Main feed query ───────────────────────────────────────────────────────────

async def get_feed(
    db: AsyncSession,
    user_id: str,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> FeedResponse:
    uid = uuid.UUID(user_id)

    # Decode cursor
    cursor_dt: Optional[datetime] = None
    cursor_id: Optional[uuid.UUID] = None
    if cursor:
        cursor_dt, cursor_id = _decode_cursor(cursor)

    # ── Pool 1: followed users' public graphs ─────────────────────────────────
    followed_subq = select(Follow.following_id).where(Follow.follower_id == uid)

    followed_query = (
        select(Graph)
        .where(
            Graph.created_by.in_(followed_subq),
            _is_public_subquery(Graph.id),
        )
        .order_by(Graph.created_at.desc(), Graph.id.desc())
    )
    if cursor_dt and cursor_id:
        followed_query = followed_query.where(
            or_(
                Graph.created_at < cursor_dt,
                and_(Graph.created_at == cursor_dt, Graph.id < cursor_id),
            )
        )

    followed_result = await db.execute(followed_query.limit(limit * 2))
    followed_graphs = followed_result.scalars().all()

    # ── Pool 2: discovery — public graphs from non-followed users ─────────────
    discovery_query = (
        select(Graph)
        .where(
            Graph.created_by != uid,
            Graph.created_by.not_in(followed_subq),
            _is_public_subquery(Graph.id),
        )
        .order_by(Graph.created_at.desc(), Graph.id.desc())
    )
    if cursor_dt and cursor_id:
        discovery_query = discovery_query.where(
            or_(
                Graph.created_at < cursor_dt,
                and_(Graph.created_at == cursor_dt, Graph.id < cursor_id),
            )
        )

    discovery_result = await db.execute(discovery_query.limit(limit))
    discovery_graphs = discovery_result.scalars().all()

    # ── Interleave: 1 discovery per 3 followed ────────────────────────────────
    interleaved: list[tuple[Graph, bool]] = []  # (graph, is_discovery)
    fi, di = 0, 0

    while len(interleaved) < limit + 1:
        # Add up to 3 followed items
        for _ in range(3):
            if fi < len(followed_graphs) and len(interleaved) < limit + 1:
                interleaved.append((followed_graphs[fi], False))
                fi += 1
        # Add 1 discovery item
        if di < len(discovery_graphs) and len(interleaved) < limit + 1:
            interleaved.append((discovery_graphs[di], True))
            di += 1
        # Break if both pools exhausted
        if fi >= len(followed_graphs) and di >= len(discovery_graphs):
            break

    # ── Pagination ────────────────────────────────────────────────────────────
    has_more = len(interleaved) > limit
    if has_more:
        interleaved = interleaved[:limit]

    next_cursor = None
    if has_more and interleaved:
        last_graph, _ = interleaved[-1]
        next_cursor = _encode_cursor(last_graph.created_at, last_graph.id)

    # ── Build response items ──────────────────────────────────────────────────
    items = []
    for graph, is_discovery in interleaved:
        item = await _build_feed_item(db, graph, is_discovery)
        items.append(item)

    return FeedResponse(items=items, next_cursor=next_cursor, has_more=has_more)
