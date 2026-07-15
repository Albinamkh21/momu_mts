"""DraftRepository — CRUD for ui_track_drafts."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from models import UITrackDraft


class DraftRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: Optional[int] = None,
        payload: Optional[dict] = None,
        track_id: Optional[int] = None,
    ) -> UITrackDraft:
        draft = UITrackDraft(user_id=user_id, status="draft", payload=payload or {}, track_id=track_id)
        self.db.add(draft)
        self.db.flush()
        return draft

    def get_by_id(self, draft_id: uuid.UUID) -> Optional[UITrackDraft]:
        return self.db.query(UITrackDraft).filter(UITrackDraft.id == draft_id).first()

    def update_payload(self, draft: UITrackDraft, patch: dict) -> UITrackDraft:
        """Shallow-merge patch keys into existing payload."""
        current = dict(draft.payload or {})
        current.update(patch)
        draft.payload = current
        self.db.flush()
        return draft

    def set_status(self, draft: UITrackDraft, status: str) -> UITrackDraft:
        draft.status = status
        self.db.flush()
        return draft

    def delete(self, draft: UITrackDraft) -> None:
        self.db.delete(draft)
        self.db.flush()
