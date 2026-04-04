"""
Graph service — all business logic for graphs, edges, and shifts.
"""
import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.models import Edge, Graph, Node
from app.schemas.schemas import (
    EdgeCreate,
    GraphCreate,
    GraphDetail,
    GraphShift,
    GraphUpdate,
    NodeInGraph,
    EdgeOut,
)

MAX_CONTEXT_NODES = 4  # 1 key + 4 context = 5 total


async def _get_graph_or_404(db: AsyncSession, graph_id: uuid.UUID) -> Graph:
    result = await db.execute(
        select(Graph)
        .where(Graph.id == graph_id)
        .options(
            selectinload(Graph.edges),
            selectinload(Graph.key_node),
        )
    )
    graph = result.scalar_one_or_none()
    if not graph:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph not found")
    return graph


async def _assert_owner(graph: Graph, user_id: str) -> None:
    if str(graph.created_by) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your graph")


async def _build_graph_detail(db: AsyncSession, graph: Graph) -> GraphDetail:
    """Assemble a GraphDetail response, annotating which node is the key node."""
    # Collect all node IDs in this graph
    context_node_ids = [e.source_node_id for e in graph.edges]
    all_node_ids = [graph.key_node_id] + context_node_ids

    nodes_result = await db.execute(select(Node).where(Node.id.in_(all_node_ids)))
    nodes = nodes_result.scalars().all()

    nodes_in_graph = [
        NodeInGraph(**{**node.__dict__, "is_key": node.id == graph.key_node_id})
        for node in nodes
    ]

    edges_out = [EdgeOut.model_validate(e) for e in graph.edges]

    return GraphDetail(
        **{k: v for k, v in graph.__dict__.items() if not k.startswith("_")},
        nodes=nodes_in_graph,
        edges=edges_out,
    )


async def create_graph(
    db: AsyncSession, payload: GraphCreate, user_id: str
) -> GraphDetail:
    # Verify key node exists and belongs to the user (or is accessible)
    node_result = await db.execute(select(Node).where(Node.id == payload.key_node_id))
    node = node_result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Key node not found")

    graph = Graph(
        title=payload.title,
        description=payload.description,
        key_node_id=payload.key_node_id,
        created_by=uuid.UUID(user_id),
    )
    db.add(graph)
    await db.flush()  # get graph.id before building detail
    await db.refresh(graph, ["edges", "key_node"])
    return await _build_graph_detail(db, graph)


async def get_graph(
    db: AsyncSession, graph_id: uuid.UUID, user_id: str
) -> GraphDetail:
    graph = await _get_graph_or_404(db, graph_id)
    await _assert_can_read(db, graph, user_id)
    return await _build_graph_detail(db, graph)


async def _assert_can_read(db: AsyncSession, graph: Graph, user_id: str) -> None:
    """Owner can always read. Others need a share record."""
    if str(graph.created_by) == user_id:
        return
    from app.models.models import Share
    share_result = await db.execute(
        select(Share).where(
            Share.graph_id == graph.id,
            (Share.shared_with == uuid.UUID(user_id)) | (Share.share_type == "public"),
        )
    )
    if not share_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")


async def update_graph(
    db: AsyncSession, graph_id: uuid.UUID, payload: GraphUpdate, user_id: str
) -> GraphDetail:
    graph = await _get_graph_or_404(db, graph_id)
    await _assert_owner(graph, user_id)

    if payload.title is not None:
        graph.title = payload.title
    if payload.description is not None:
        graph.description = payload.description

    await db.flush()
    await db.refresh(graph, ["edges", "key_node"])
    return await _build_graph_detail(db, graph)


async def delete_graph(
    db: AsyncSession, graph_id: uuid.UUID, user_id: str
) -> None:
    graph = await _get_graph_or_404(db, graph_id)
    await _assert_owner(graph, user_id)
    await db.delete(graph)


async def add_edge(
    db: AsyncSession, graph_id: uuid.UUID, payload: EdgeCreate, user_id: str
) -> GraphDetail:
    graph = await _get_graph_or_404(db, graph_id)
    await _assert_owner(graph, user_id)

    # Enforce max 4 context nodes
    if len(graph.edges) >= MAX_CONTEXT_NODES:
        raise HTTPException(
            status_code=400,
            detail=f"Graph already has the maximum of {MAX_CONTEXT_NODES} context nodes",
        )

    # Verify context node exists
    node_result = await db.execute(
        select(Node).where(Node.id == payload.source_node_id)
    )
    if not node_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Context node not found")

    # Prevent duplicate
    existing = await db.execute(
        select(Edge).where(
            Edge.graph_id == graph_id,
            Edge.source_node_id == payload.source_node_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This node is already a context node in this graph")

    # Prevent pointing at itself
    if payload.source_node_id == graph.key_node_id:
        raise HTTPException(status_code=400, detail="Context node cannot be the key node")

    edge = Edge(
        graph_id=graph_id,
        source_node_id=payload.source_node_id,
        target_node_id=graph.key_node_id,
        relationship_type="context_for",
    )
    db.add(edge)
    await db.flush()
    await db.refresh(graph, ["edges", "key_node"])
    return await _build_graph_detail(db, graph)


async def remove_edge(
    db: AsyncSession, graph_id: uuid.UUID, edge_id: uuid.UUID, user_id: str
) -> GraphDetail:
    graph = await _get_graph_or_404(db, graph_id)
    await _assert_owner(graph, user_id)

    edge_result = await db.execute(
        select(Edge).where(Edge.id == edge_id, Edge.graph_id == graph_id)
    )
    edge = edge_result.scalar_one_or_none()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")

    await db.delete(edge)
    await db.flush()
    await db.refresh(graph, ["edges", "key_node"])
    return await _build_graph_detail(db, graph)


async def shift_graph(
    db: AsyncSession, graph_id: uuid.UUID, payload: GraphShift, user_id: str
) -> GraphDetail:
    """
    Fork a graph into a new one.
    - 'with_context': new graph copies all existing edges (same context nodes).
    - 'fresh': new graph starts with only the key node, no edges.
    """
    graph = await _get_graph_or_404(db, graph_id)
    await _assert_owner(graph, user_id)

    new_graph = Graph(
        title=payload.title or graph.title,
        description=payload.description or graph.description,
        key_node_id=graph.key_node_id,
        created_by=uuid.UUID(user_id),
        parent_graph_id=graph.id,
        shift_type=payload.shift_type,
    )
    db.add(new_graph)
    await db.flush()

    if payload.shift_type == "with_context":
        for edge in graph.edges:
            new_edge = Edge(
                graph_id=new_graph.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                relationship_type="context_for",
            )
            db.add(new_edge)
        await db.flush()

    await db.refresh(new_graph, ["edges", "key_node"])
    return await _build_graph_detail(db, new_graph)


async def list_user_graphs(
    db: AsyncSession,
    user_id: str,
    cursor: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """Cursor-based paginated list of graphs for a user."""
    from datetime import datetime, timezone

    query = (
        select(Graph)
        .where(Graph.created_by == uuid.UUID(user_id))
        .order_by(Graph.created_at.desc())
        .limit(limit + 1)
    )

    if cursor:
        # cursor is an ISO timestamp
        cursor_dt = datetime.fromisoformat(cursor)
        query = query.where(Graph.created_at < cursor_dt)

    result = await db.execute(query)
    graphs = result.scalars().all()

    has_more = len(graphs) > limit
    if has_more:
        graphs = graphs[:limit]

    next_cursor = None
    if has_more and graphs:
        next_cursor = graphs[-1].created_at.isoformat()

    return {
        "items": [
            {**{k: v for k, v in g.__dict__.items() if not k.startswith("_")}}
            for g in graphs
        ],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
