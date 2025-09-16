from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .routes import players, tournaments, matches

# create tables (for simple local usage)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Snooker Tournament API (fixed)")

app.include_router(players.router)
app.include_router(tournaments.router)
app.include_router(matches.router)

@app.get("/health")
def health():
    return {"ok": True}
