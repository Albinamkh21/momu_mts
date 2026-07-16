"""FastAPI router for track draft CRUD."""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import SessionLocal
from __schemas.drafts import (
    DraftCreateRequest,
    DraftPatchRequest,
    DraftResponse,
    ActivationResult,
)
from services.draft_service import DraftService
from services.track_activation_service import TrackActivationService

router = APIRouter()


class RightHolderCreate(BaseModel):
    name: str
    effective_date: Optional[str] = None
    termination_date: Optional[str] = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _parse_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


# ─── POST /drafts ─────────────────────────────────────────────────────────────

@router.post("/drafts", response_model=DraftResponse, status_code=201)
def create_draft(body: DraftCreateRequest = DraftCreateRequest(), db: Session = Depends(get_db)):
    """Create a new empty track draft and return its id."""
    svc = DraftService(db)
    draft = svc.create_draft(user_id=body.user_id)
    db.commit()
    return draft


# ─── POST /drafts/from-track/{track_id} ──────────────────────────────────────

@router.post("/drafts/from-track/{track_id}", response_model=DraftResponse, status_code=201)
def create_draft_from_track(track_id: int, db: Session = Depends(get_db)):
    """Create a draft pre-filled from an existing track's data, for editing."""
    svc = DraftService(db)
    try:
        draft = svc.create_draft_for_track(track_id)
        db.commit()
        return draft
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ─── PATCH /drafts/{draft_id} ────────────────────────────────────────────────

@router.patch("/drafts/{draft_id}", response_model=DraftResponse)
def patch_draft(draft_id: uuid.UUID, body: DraftPatchRequest, db: Session = Depends(get_db)):
    """Merge step data into the draft payload."""
    svc = DraftService(db)
    try:
        result = svc.patch_draft(draft_id, body)
        db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ─── GET /drafts/{draft_id} ──────────────────────────────────────────────────

@router.get("/drafts/{draft_id}", response_model=DraftResponse)
def get_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch a draft by id."""
    svc = DraftService(db)
    try:
        draft = svc.get_draft(draft_id)
        return DraftResponse.model_validate(draft)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ─── POST /drafts/{draft_id}/activate ────────────────────────────────────────

@router.post("/drafts/{draft_id}/activate", response_model=ActivationResult)
def activate_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Activate a draft: write to production tables and delete the draft."""
    svc = TrackActivationService(db)
    try:
        return svc.activate_draft(draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Reference data endpoints (used by wizard forms) ─────────────────────────

@router.get("/drafts-ref/right-holders")
def get_right_holders(db: Session = Depends(get_db)):
    from sqlalchemy import text
    rows = db.execute(text("SELECT id, name FROM right_holder ORDER BY name")).fetchall()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.post("/right-holders", status_code=201)
def create_right_holder(body: RightHolderCreate, db: Session = Depends(get_db)):
    """Create a new right holder (used from the wizard's rights step when the
    needed right holder does not exist yet). Deduplicates by name."""
    from sqlalchemy import text

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    existing = db.execute(
        text(
            "SELECT id, name, effective_date, termination_date "
            "FROM right_holder WHERE name = :name"
        ),
        {"name": name},
    ).fetchone()
    if existing:
        return {
            "id": existing.id,
            "name": existing.name,
            "effective_date": str(existing.effective_date) if existing.effective_date else None,
            "termination_date": str(existing.termination_date) if existing.termination_date else None,
        }

    effective_date = _parse_date(body.effective_date)
    termination_date = _parse_date(body.termination_date)

    result = db.execute(
        text(
            "INSERT INTO right_holder (name, effective_date, termination_date) "
            "VALUES (:name, :eff, :term) "
            "RETURNING id, name, effective_date, termination_date"
        ),
        {"name": name, "eff": effective_date, "term": termination_date},
    ).fetchone()
    db.commit()
    return {
        "id": result.id,
        "name": result.name,
        "effective_date": str(result.effective_date) if result.effective_date else None,
        "termination_date": str(result.termination_date) if result.termination_date else None,
    }


@router.get("/drafts-ref/right-categories")
def get_right_categories(db: Session = Depends(get_db)):
    from sqlalchemy import text
    rows = db.execute(text("SELECT id, name FROM right_category ORDER BY name")).fetchall()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/drafts-ref/right-usage-types")
def get_right_usage_types(db: Session = Depends(get_db)):
    from sqlalchemy import text
    rows = db.execute(text("SELECT id, code, name FROM right_usage_type ORDER BY name")).fetchall()
    return [{"id": r.id, "code": r.code, "name": r.name} for r in rows]


@router.get("/drafts-ref/releases")
def get_releases(db: Session = Depends(get_db)):
    from sqlalchemy import text
    rows = db.execute(
        text("SELECT id, title, upc FROM \"release\" ORDER BY title LIMIT 500")
    ).fetchall()
    return [{"id": r.id, "title": r.title, "upc": r.upc} for r in rows]


@router.get("/drafts-ref/persons")
def search_persons(q: str = "", db: Session = Depends(get_db)):
    from sqlalchemy import text
    rows = db.execute(
        text("SELECT id, full_name FROM person WHERE full_name ILIKE :q ORDER BY full_name LIMIT 50"),
        {"q": f"%{q}%"},
    ).fetchall()
    return [{"id": r.id, "full_name": r.full_name} for r in rows]
