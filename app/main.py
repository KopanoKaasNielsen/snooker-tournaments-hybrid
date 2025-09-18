from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .routes import players, tournaments, matches
from fastapi import FastAPI
from .database import engine, Base
from .routes import players, tournaments, matches
# create tables (for simple local usage)


app = FastAPI()
# Optional: table creation at startup (not recommended for prod)
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

app.include_router(players.router)
app.include_router(tournaments.router)
app.include_router(matches.router)



app.include_router(players.router)
app.include_router(tournaments.router)
app.include_router(matches.router)

@app.get("/health")
def health():
    return {"ok": True}
