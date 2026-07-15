"""DraftService — validates and persists draft payload patches."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from __crud.draft_repository import DraftRepository
from __schemas.drafts import DraftPatchRequest, DraftResponse
from models import UITrackDraft


class DraftService:
    def __init__(self, db: Session):
        self.repo = DraftRepository(db)

    def create_draft(self, user_id: Optional[int] = None) -> DraftResponse:
        draft = self.repo.create(user_id=user_id)
        return DraftResponse.model_validate(draft)

    def create_draft_for_track(self, track_id: int, user_id: Optional[int] = None) -> DraftResponse:
        """Create a draft pre-filled with an existing track's data, for editing."""
        payload = self._build_payload_from_track(track_id)
        draft = self.repo.create(user_id=user_id, payload=payload, track_id=track_id)
        return DraftResponse.model_validate(draft)

    def _build_payload_from_track(self, track_id: int) -> dict:
        db = self.repo.db

        track_row = db.execute(
            text("""
                SELECT id, title, isrc, duration, explicit, resource_reference, label_own_code
                FROM track WHERE id = :tid
            """),
            {"tid": track_id},
        ).fetchone()
        if track_row is None:
            raise ValueError(f"Track {track_id} not found")

        label_row = db.execute(
            text("SELECT label_id FROM track_label WHERE track_id = :tid LIMIT 1"),
            {"tid": track_id},
        ).fetchone()

        step1 = {
            "title": track_row.title,
            "isrc": track_row.isrc,
            "duration": track_row.duration,
            "explicit": bool(track_row.explicit),
            "resource_reference": track_row.resource_reference,
            "label_id": label_row.label_id if label_row else None,
            "label_own_code": track_row.label_own_code,
        }

        release_row = db.execute(
            text("""
                SELECT r.id
                FROM "release" r
                JOIN track_release tr ON tr.release_id = r.id
                WHERE tr.track_id = :tid
                LIMIT 1
            """),
            {"tid": track_id},
        ).fetchone()
        step2 = {"release_id": release_row.id if release_row else None}

        valid_roles = {"artist_name", "composer", "lyricist"}
        contributor_rows = db.execute(
            text("""
                SELECT tc.person_id, p.full_name, tc.role
                FROM track_contribution tc
                JOIN person p ON p.id = tc.person_id
                WHERE tc.track_id = :tid
                ORDER BY tc.role, p.full_name
            """),
            {"tid": track_id},
        ).fetchall()
        step3 = {
            "contributors": [
                {"person_id": r.person_id, "full_name": r.full_name, "role": r.role}
                for r in contributor_rows
                if r.role in valid_roles
            ]
        }

        right_rows = db.execute(
            text("""
                SELECT right_holder_id, right_category_id, right_usage_type_id,
                       contract_id, share_percentage, region_id
                FROM track_right
                WHERE track_id = :tid
            """),
            {"tid": track_id},
        ).fetchall()
        step4 = {
            "rights": [
                {
                    "right_holder_id": r.right_holder_id,
                    "right_category_id": r.right_category_id,
                    "right_usage_type_id": r.right_usage_type_id,
                    "contract_id": r.contract_id,
                    "share_percentage": float(r.share_percentage) if r.share_percentage is not None else 0,
                    "region_id": r.region_id,
                }
                for r in right_rows
            ]
        }

        return {"step1": step1, "step2": step2, "step3": step3, "step4": step4}

    def get_draft(self, draft_id: uuid.UUID) -> UITrackDraft:
        draft = self.repo.get_by_id(draft_id)
        if draft is None:
            raise ValueError(f"Draft {draft_id} not found")
        return draft

    def patch_draft(self, draft_id: uuid.UUID, patch: DraftPatchRequest) -> DraftResponse:
        draft = self.get_draft(draft_id)

        # Only include steps that were actually sent in the request.
        # mode="json" ensures values that aren't natively JSON-serializable
        # (e.g. Decimal from DraftRight.share_percentage) are converted to
        # JSON-safe types before being stored in the JSONB payload column.
        patch_data = patch.model_dump(exclude_none=True, mode="json")

        self.repo.update_payload(draft, patch_data)
        return DraftResponse.model_validate(draft)
