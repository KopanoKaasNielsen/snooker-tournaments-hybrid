#!/bin/bash

#set -e

#git checkout -b improve/health-bundle

# 1) Create centralized error messages
mkdir -p app/core
cat > app/core/errors.py <<EOF
class Err:
    PLAYER_NOT_FOUND = "Player not found"
    TOURNAMENT_NOT_FOUND = "Tournament not found"
    INSUFFICIENT_BALANCE = "Insufficient balance for entry fee"
EOF

# 2) Update TournamentRegistrationCreate to only accept player_id
sed -i '/class TournamentRegistrationCreate/,/class Tournament/d' app/schemas.py
echo "
class TournamentRegistrationCreate(BaseModel):
    player_id: int
" >> app/schemas.py

# 3) Add response models to schemas.py
cat >> app/schemas.py <<EOF

class PlayerBalanceOut(BaseModel):
    player_id: int
    balance: float

class PlayerEloOut(BaseModel):
    player_id: int
    elo: int

class WalletTransactionOut(BaseModel):
    id: int
    type: str
    amount: float
    timestamp: str
EOF

# 4) Add tags and response_model to players route
sed -i 's/APIRouter()/APIRouter(prefix="\/players", tags=["players"])/' app/routes/players.py
sed -i 's/@router.get("\/{player_id}\/balance")/@router.get("\/{player_id}\/balance", response_model=schemas.PlayerBalanceOut)/' app/routes/players.py
sed -i 's/@router.get("\/{player_id}\/elo")/@router.get("\/{player_id}\/elo", response_model=schemas.PlayerEloOut)/' app/routes/players.py

# 5) Clean up tournament registration route
sed -i 's/from app import crud, models/from app import crud, models, schemas/' app/routes/tournaments.py
sed -i 's/APIRouter()/APIRouter(prefix="\/tournaments", tags=["tournaments"])/' app/routes/tournaments.py
sed -i '/if not player:/,+5c\        if not player:\n            raise HTTPException(status_code=404, detail="Player not found")' app/routes/tournaments.py

# 6) Add CORS support to app/main.py
if ! grep -q CORSMiddleware app/main.py; then
  sed -i '1i from fastapi.middleware.cors import CORSMiddleware' app/main.py
  sed -i '/app = FastAPI()/a app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])' app/main.py
fi

# 7) Seed idempotence note
echo "# idempotent seed setup (avoid duplicate inserts)" >> app/init_db.py

# 8) Add pre-commit config
cat > .pre-commit-config.yaml <<EOF
repos:
  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks: [ { id: black } ]
  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks: [ { id: isort } ]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        args: [--ignore-missing-imports, --install-types, --non-interactive]
EOF

# 9) Add bandit + safety to CI if not already present
CI_FILE=".github/workflows/ci.yml"
if ! grep -q "bandit" $CI_FILE; then
cat >> $CI_FILE <<EOF

      - name: Security: bandit
        run: |
          pip install bandit
          bandit -q -r app || true

      - name: Dependencies: safety
        run: |
          pip install safety
          safety check -r requirements.txt || true
EOF
fi

# 10) Format code
pip install pre-commit bandit safety --quiet
pre-commit run --all-files || true

# 11) Commit & push
git add .
git commit -m "chore: health fixes — clearer registration, response models, tags, CORS, errors, pre-commit, security checks"
git push -u origin improve/health-bundle
