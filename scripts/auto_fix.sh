#!/usr/bin/env bash
set -euo pipefail

# ---------- helpers ----------
append_if_missing () {
  local FILE="$1"
  local LINE="$2"
  grep -qxF "$LINE" "$FILE" || echo "$LINE" >> "$FILE"
}

require_git_repo () {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo "❌ Not inside a Git repo. Run this from your repo root."; exit 1;
  }
}

# ---------- preflight ----------
require_git_repo
REPO_NAME="$(basename "$(git rev-parse --show-toplevel)")"
echo "📦 Repo: $REPO_NAME"

# Safety branch + safety commit
BRANCH="chore/auto-fix-$(date +%Y%m%d-%H%M%S)"
echo "🛟 Creating safety branch: $BRANCH"
git switch -c "$BRANCH" || git checkout -b "$BRANCH"

echo "🔎 Staging current changes (if any) for a safety commit"
git add -A || true
if ! git diff --cached --quiet; then
  git commit -m "chore: safety snapshot before auto-fix"
else
  echo "ℹ️ Nothing staged for safety commit."
fi

# ---------- .gitignore hardening ----------
echo "🧹 Hardening .gitignore"
touch .gitignore
append_if_missing .gitignore "__pycache__/"
append_if_missing .gitignore "*.pyc"
append_if_missing .gitignore "*.pyo"
append_if_missing .gitignore ".pytest_cache/"
append_if_missing .gitignore ".coverage"
append_if_missing .gitignore "venv/"
append_if_missing .gitignore "*.db"
append_if_missing .gitignore ".mypy_cache/"
append_if_missing .gitignore ".DS_Store"

# ---------- untrack junk already in Git index ----------
echo "🗑️  Untracking cached junk from Git (keeps files locally)"
# shellcheck disable=SC2046
git rm -r --cached -f --ignore-unmatch $(git ls-files -z | tr '\0' '\n' \
  | grep -E '(^|/)(__pycache__/|.*\.(pyc|pyo)$|\.pytest_cache/|\.coverage$|venv/|.*\.db$|\.mypy_cache/|\.DS_Store$)' || true)

# ---------- local cleanup (does not touch venv) ----------
echo "🧼 Local cleanup"
find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
rm -rf .pytest_cache .mypy_cache 2>/dev/null || true

# ---------- solid pytest conftest ----------
echo "🧪 Installing a solid tests/conftest.py (backing up existing)"
mkdir -p tests
if [ -f tests/conftest.py ]; then
  cp tests/conftest.py tests/conftest.py.bak.$(date +%s)
fi

cat > tests/conftest.py <<"PY"
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import DB primitives directly from your app's DB module
from app.database import Base, get_db
from app.main import app

# Single in-memory SQLite database shared across tests
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # One memory DB for the whole process
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def _create_schema_once():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture()
def db_session():
    # Wrap each test in a transaction and roll it back
    connection = engine.connect()
    txn = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        txn.rollback()
        connection.close()

@pytest.fixture(autouse=True)
def _override_get_db(monkeypatch, db_session):
    def _get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _get_db
PY

# ---------- scan for duplicate models/tablenames ----------
echo "🔍 Scanning app/models.py for duplicate __tablename__ or model class names"
mkdir -p scripts
cat > scripts/find_duplicate_models.py <<"PY"
import re
from collections import Counter

path = "app/models.py"
try:
    src = open(path, "r", encoding="utf-8").read()
except FileNotFoundError:
    print("⚠️  app/models.py not found; skipping duplicate scan.")
    raise SystemExit(0)

# crude regexes – good enough to flag likely issues
tablenames = re.findall(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]", src)
classes = re.findall(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(Base\)\s*:", src, flags=re.M)

dup_tabs = [t for t, c in Counter(tablenames).items() if c > 1]
dup_classes = [t for t, c in Counter(classes).items() if c > 1]

if not dup_tabs and not dup_classes:
    print("✅ No duplicate __tablename__ or model class names detected in app/models.py")
else:
    if dup_tabs:
        print("❌ Duplicate __tablename__ values detected:", ", ".join(dup_tabs))
    if dup_classes:
        print("❌ Duplicate model class names detected:", ", ".join(dup_classes))
    print("\n👉 Open app/models.py and remove duplicate declarations. "
          "You should have exactly one class per table name.")
PY

python3 scripts/find_duplicate_models.py || true

# ---------- commit ----------
echo "📝 Committing changes"
git add .gitignore tests/conftest.py scripts/auto_fix.sh scripts/find_duplicate_models.py || true
if ! git diff --cached --quiet; then
  git commit -m "chore: repo hygiene, solid pytest DB fixture, duplicate model scan"
else
  echo "ℹ️ Nothing new to commit."
fi

echo
echo "✅ Auto-fix finished on branch: $BRANCH"
echo "Next:"
echo "  1) Run tests:     pytest -q"
echo "  2) If tests pass: git push -u origin $BRANCH"
echo "  3) Open a PR into your target branch (e.g. main)."
echo
echo "If the duplicate scan reported issues, open app/models.py and remove any duplicate"
echo "model classes or repeated __tablename__ entries, then run pytest again."
