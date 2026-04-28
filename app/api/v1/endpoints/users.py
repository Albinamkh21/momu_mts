from fastapi import APIRouter
from sqlalchemy import text
from core.database import sync_engine

router = APIRouter()


@router.get("/users")
def get_users():
    try:
        with sync_engine.connect() as conn:
            rows = conn.execute(text('SELECT id, login FROM "user" ORDER BY login'))
            users = [{"id": r.id, "login": r.login} for r in rows.fetchall()]
        return users
    except Exception:
        return []
