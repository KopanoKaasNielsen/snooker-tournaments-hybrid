"""Check runtime isolation, disposable migrated startup, and the preserved API snapshot."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import importlib.util
import json
import os
import secrets
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def check_contract(current: dict) -> None:
    baseline = json.loads((ROOT / "docs/authentication-openapi.json").read_text())
    assert current == baseline, "Authentication API contract snapshot differs"
    print("Authentication API contract matches the reviewed additive snapshot.")


async def check_startup(app) -> None:
    async with app.router.lifespan_context(app):
        for path, status, expected in [
            ("/health", 200, {"ok": True}),
            (
                "/players/",
                401,
                {"detail": "Session expired or invalid. Please sign in."},
            ),
            (
                "/tournaments/",
                401,
                {"detail": "Session expired or invalid. Please sign in."},
            ),
            (
                "/matches/",
                401,
                {"detail": "Session expired or invalid. Please sign in."},
            ),
            (
                "/players/1/balance",
                401,
                {"detail": "Session expired or invalid. Please sign in."},
            ),
        ]:
            messages = []
            request_sent = False
            disconnected = asyncio.Event()

            async def receive():
                nonlocal request_sent
                if not request_sent:
                    request_sent = True
                    return {"type": "http.request", "body": b"", "more_body": False}
                # A real ASGI server waits here until disconnection; repeatedly
                # returning a request event can starve streaming response tasks.
                await disconnected.wait()
                return {"type": "http.disconnect"}

            async def send(message):
                messages.append(message)

            await app(
                {
                    "type": "http",
                    "asgi": {"version": "3.0"},
                    "http_version": "1.1",
                    "method": "GET",
                    "scheme": "http",
                    "path": path,
                    "raw_path": path.encode(),
                    "query_string": b"",
                    "headers": [],
                    "server": ("test", 80),
                    "client": ("127.0.0.1", 1234),
                    "root_path": "",
                },
                receive,
                send,
            )
            assert messages[0]["status"] == status, path
            body = b"".join(message.get("body", b"") for message in messages)
            assert json.loads(body) == expected, path
    print(
        "Migrated startup, health and unauthenticated-denial checks passed (direct ASGI; no test client)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-only", action="store_true")
    args = parser.parse_args()
    if args.runtime_only:
        for name in ("pytest", "black", "httpx", "httpx2"):
            assert (
                importlib.util.find_spec(name) is None
            ), f"Development dependency present: {name}"
    with tempfile.TemporaryDirectory(
        prefix="snooker-runtime-verification-"
    ) as directory:
        os.environ["AUTH_SECRET_KEY"] = secrets.token_urlsafe(64)
        os.environ["APP_ENV"] = "development"
        os.environ["AUTH_COOKIE_SECURE"] = "false"
        os.environ["AUTH_ALLOWED_ORIGINS"] = "http://127.0.0.1:5173"
        os.environ["DATABASE_URL"] = f"sqlite:///{directory}/runtime.db"
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True
        )
        # Import the dormant settings module without reading a repository .env file.
        previous = Path.cwd()
        try:
            os.chdir(directory)
            for file in (ROOT / "app").rglob("*.py"):
                module = ".".join(file.relative_to(ROOT).with_suffix("").parts)
                importlib.import_module(module)
            from app.main import app

            check_contract(app.openapi())
            asyncio.run(check_startup(app))
        finally:
            os.chdir(previous)


if __name__ == "__main__":
    main()
