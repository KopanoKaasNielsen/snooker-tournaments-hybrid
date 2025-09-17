#!/bin/bash

set -e

echo "🔧 Fixing 'Column(float)' to use SQLAlchemy Float..."
sed -i 's/from sqlalchemy import /from sqlalchemy import Float, /' app/models.py
sed -i 's/Column(float/Column(Float/g' app/models.py
echo "✅ Model fixed."

echo "🔧 Fixing improper schema references in players.py..."
sed -i 's/__import__(.*).PlayerBalanceOut/schemas.PlayerBalanceOut/' app/routes/players.py
sed -i 's/__import__(.*).PlayerEloOut/schemas.PlayerEloOut/' app/routes/players.py

# Ensure 'from app import schemas' is in players.py
if ! grep -q "from app import schemas" app/routes/players.py; then
  sed -i '/from app import crud, models/a from app import schemas' app/routes/players.py
  echo "✅ Added missing 'from app import schemas' import"
else
  echo "✅ 'schemas' already imported"
fi

echo "🔄 Pulling latest from GitHub for 'improve/health-bundle'..."
git checkout improve/health-bundle
git pull origin improve/health-bundle

echo "🧪 Running tests..."
pytest -q --tb=short --disable-warnings

echo "✅ All done. You’re ready to open or update your PR!"
