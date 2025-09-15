# Snooker Tournament Backend (FastAPI + SQLAlchemy)

Clean architecture for managing snooker tournaments.

## Quickstart
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
alembic upgrade head

uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs
