from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  # ensure models are registered with SQLAlchemy metadata
from .database import Base, engine
from .routes import matches, players, tournaments

app = FastAPI()

# Ensure default database tables exist when the module loads.
Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


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
