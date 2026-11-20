"""Check runtime isolation, disposable migrated startup, and the preserved API snapshot."""

from __future__ import annotations

import argparse
import asyncio
import copy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def check_contract(current: dict) -> None:
    current = copy.deepcopy(current)
    baseline = json.loads((ROOT / "docs/backend-openapi.json").read_text())
    # New FastAPI documents optional validation error context/input. Neither changes
    # request validation or successful responses; do not normalize application schemas.
    properties = current["components"]["schemas"]["ValidationError"]["properties"]
    for name in ("ctx", "input"):
        assert (
            name not in current["components"]["schemas"]["ValidationError"]["required"]
        )
        properties.pop(name, None)
    assert (
        current == baseline
    ), "API snapshot differs beyond reviewed framework error details"
    print(
        "API snapshot matches: only optional framework ValidationError ctx/input additions."
    )


async def check_startup(app) -> None:
    async with app.router.lifespan_context(app):
        for path, status, expected in [
            ("/health", 200, {"ok": True}),
            ("/players/", 200, []),
            ("/tournaments/", 200, []),
            ("/matches/", 200, []),
            ("/players/1/balance", 404, {"detail": "Player not found"}),
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
        "Migrated startup/health/list/balance-404 checks passed (direct ASGI; no test client)."
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
