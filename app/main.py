from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import (
    models,
)  # noqa: F401  # ensure models are registered with SQLAlchemy metadata
from .database import engine
from .routes import matches, players, tournaments


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Schema changes and demo inserts belong to explicit commands, never startup.
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(lifespan=lifespan)

# Basic CORS configuration for local development/testing.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(tournaments.router)
app.include_router(matches.router)


@app.get("/health")
def health():
    return {"ok": True}
