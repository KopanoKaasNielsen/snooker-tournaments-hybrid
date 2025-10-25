"""FastAPI application entry point."""

from fastapi import FastAPI

from .database import Base, engine
from .routes import matches, players, tournaments

app = FastAPI()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(players.router)
app.include_router(tournaments.router)
app.include_router(matches.router)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
