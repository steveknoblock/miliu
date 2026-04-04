# Miliu Backend — FastAPI

Context Graph Explorer API. Graphs of 1 key node + up to 4 context nodes, connected by `context_for` edges.

## Stack
- **FastAPI** + **Uvicorn**
- **SQLAlchemy 2.0** async ORM
- **PostgreSQL** (via asyncpg)
- **Alembic** for migrations
- **JWT** auth (access + refresh tokens)

## Project Structure

```
app/
├── main.py              # FastAPI app, CORS, router registration
├── core/
│   ├── config.py        # Settings (pydantic-settings, reads .env)
│   └── security.py      # JWT helpers, password hashing, auth dependency
├── db/
│   └── session.py       # Async engine, session factory, Base, get_db()
├── models/
│   └── models.py        # SQLAlchemy ORM models (User, Node, Graph, Edge, Share)
├── schemas/
│   └── schemas.py       # Pydantic request/response schemas
├── routers/
│   ├── auth.py          # POST /auth/register|login|refresh|logout
│   ├── nodes.py         # CRUD /nodes
│   └── graphs.py        # CRUD /graphs + edges + shift
└── services/
    └── graph_service.py # All graph business logic
```

## Setup

```bash
# 1. Clone and install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL and SECRET_KEY

# 3. Run database migrations
alembic upgrade head

# 4. Start the server
uvicorn app.main:app --reload
```

API docs available at: http://localhost:8000/docs

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/auth/register | Register a new user |
| POST | /api/v1/auth/login | Login, get JWT tokens |
| POST | /api/v1/auth/refresh | Rotate refresh token |
| POST | /api/v1/nodes | Create a node |
| GET | /api/v1/nodes/{id} | Get a node |
| POST | /api/v1/graphs | Create a graph (with key node) |
| GET | /api/v1/graphs | List your graphs (cursor-paginated) |
| GET | /api/v1/graphs/{id} | Get full graph with nodes & edges |
| PATCH | /api/v1/graphs/{id} | Update graph title/description |
| DELETE | /api/v1/graphs/{id} | Delete a graph |
| POST | /api/v1/graphs/{id}/edges | Add a context node (max 4) |
| DELETE | /api/v1/graphs/{id}/edges/{edge_id} | Remove a context node |
| POST | /api/v1/graphs/{id}/shift | Fork a graph (with_context or fresh) |

## Graph Rules (enforced in service layer)
- Every graph has exactly **1 key node** (`key_node_id`)
- Up to **4 context nodes** connected via `context_for` edges (5 nodes total)
- All edges point **toward** the key node (`source → target = key_node`)
- **Shift** forks a graph: `with_context` copies edges, `fresh` starts clean
