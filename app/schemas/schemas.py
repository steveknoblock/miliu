import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Node ──────────────────────────────────────────────────────────────────────

class NodeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    node_type: str = Field(default="user_post", pattern="^(user_post|web_content)$")
    metadata: Optional[dict[str, Any]] = None


class NodeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    metadata: Optional[dict[str, Any]] = None


class NodeOut(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    node_type: str
    created_by: uuid.UUID
    metadata: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NodeInGraph(NodeOut):
    """Node with is_key flag when returned inside a graph."""
    is_key: bool = False


# ── Edge ──────────────────────────────────────────────────────────────────────

class EdgeCreate(BaseModel):
    source_node_id: uuid.UUID  # The context node being added


class EdgeOut(BaseModel):
    id: uuid.UUID
    graph_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relationship_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Graph ─────────────────────────────────────────────────────────────────────

class GraphCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    key_node_id: uuid.UUID


class GraphUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class GraphShift(BaseModel):
    shift_type: str = Field(..., pattern="^(with_context|fresh)$")
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class GraphOut(BaseModel):
    id: uuid.UUID
    title: Optional[str]
    description: Optional[str]
    key_node_id: uuid.UUID
    created_by: uuid.UUID
    parent_graph_id: Optional[uuid.UUID]
    shift_type: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GraphDetail(GraphOut):
    """Full graph with nodes and edges populated."""
    nodes: list[NodeInGraph] = []
    edges: list[EdgeOut] = []


# ── Share ─────────────────────────────────────────────────────────────────────

class ShareCreate(BaseModel):
    share_type: str = Field(..., pattern="^(private|link|public)$")
    shared_with: Optional[uuid.UUID] = None  # Required for private shares
    expires_at: Optional[datetime] = None    # Optional expiry for link shares


class ShareOut(BaseModel):
    id: uuid.UUID
    graph_id: uuid.UUID
    shared_by: uuid.UUID
    shared_with: Optional[uuid.UUID]
    share_type: str
    share_token: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Feed ──────────────────────────────────────────────────────────────────────

class FeedItem(GraphOut):
    owner_username: str
    context_count: int


class CursorPage(BaseModel):
    """Generic cursor-based pagination envelope."""
    items: list
    next_cursor: Optional[str] = None
    has_more: bool = False

# ── Feed (per spec) ───────────────────────────────────────────────────────────

class FeedAuthor(BaseModel):
    id: uuid.UUID
    username: str

    model_config = {"from_attributes": True}


class FeedKeyNode(BaseModel):
    id: uuid.UUID
    title: str
    content_preview: str  # markdown stripped, max 200 chars, generated server-side

    model_config = {"from_attributes": True}


class FeedContextNode(BaseModel):
    id: uuid.UUID
    title: str

    model_config = {"from_attributes": True}


class FeedParent(BaseModel):
    id: uuid.UUID
    title: Optional[str]
    author_username: str


class FeedItemOut(BaseModel):
    id: uuid.UUID
    title: Optional[str]
    created_at: datetime
    is_public: bool
    is_discovery: bool
    shift_type: Optional[str]
    author: FeedAuthor
    key_node: FeedKeyNode
    context_nodes: list[FeedContextNode]
    parent: Optional[FeedParent]


class FeedResponse(BaseModel):
    items: list[FeedItemOut]
    next_cursor: Optional[str] = None
    has_more: bool = False

# ── Users ─────────────────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    """Public profile — no email exposed."""
    id: uuid.UUID
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileWithStats(UserProfile):
    follower_count: int
    following_count: int
    is_following: bool  # whether the requesting user follows this profile


class FollowOut(BaseModel):
    follower_id: uuid.UUID
    following_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
