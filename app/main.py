from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, graphs, nodes, shares


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: add DB init / migrations check here if needed
    yield
    # Shutdown: close connections etc.


app = FastAPI(
    title="Miliu API",
    description="Context Graph Explorer — document-focused social web app",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(nodes.router, prefix=API_PREFIX)
app.include_router(graphs.router, prefix=API_PREFIX)
app.include_router(shares.router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}
