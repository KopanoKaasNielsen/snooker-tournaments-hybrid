from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import (
    models,
)  # noqa: F401  # ensure models are registered with SQLAlchemy metadata
from .database import engine
from .routes import admin, auth, matches, players, tournaments
from .auth_config import allowed_origins, get_auth_config


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Schema changes and demo inserts belong to explicit commands, never startup.
    get_auth_config()
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(lifespan=lifespan)

# Basic CORS configuration for local development/testing.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(players.router)
app.include_router(tournaments.router)
app.include_router(matches.router)


@app.get("/health")
def health():
    return {"ok": True}


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    response = JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
    )
    if request.url.path.startswith("/auth/"):
        response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/auth/refresh" and exc.status_code == 401:
            auth.clear_cookie(response)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Never echo submitted passwords or token-like input into validation responses.
    errors = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(errors)},
        headers={"Cache-Control": "no-store"},
    )


@app.middleware("http")
async def private_response_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/auth/", "/admin/", "/players/")):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
