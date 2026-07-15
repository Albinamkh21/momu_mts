"""TrackActivationService — 'activates' a draft by writing to production tables."""
from __future__ import annotations

import uuid
import decimal
import logging

from sqlalchemy.orm import Session

from __crud.draft_repository import DraftRepository
from __crud.track_repository import TrackRepository
from __crud.person_repository import PersonRepository
from __schemas.drafts import DraftPayload, ActivationResult

logger = logging.getLogger(__name__)


class TrackActivationService:
    def __init__(self, db: Session):
        self.db = db
        self.draft_repo = DraftRepository(db)
        self.track_repo = TrackRepository(db)
        self.person_repo = PersonRepository(db)

    def activate_draft(self, draft_id: uuid.UUID) -> ActivationResult:
        draft = self.draft_repo.get_by_id(draft_id)
        if draft is None:
            raise ValueError(f"Draft {draft_id} not found")
        if draft.status == "activated":
            raise ValueError("Draft is already activated")

        try:
            self.draft_repo.set_status(draft, "activating")
            if draft.track_id:
                track_id = self._update(draft.track_id, draft.payload or {})
                message = "Track updated successfully"
            else:
                track_id = self._activate(draft.payload or {})
                message = "Track created successfully"
            self.draft_repo.delete(draft)
            self.db.commit()
            return ActivationResult(track_id=track_id, message=message)

        except Exception as exc:
            self.db.rollback()
            # Re-fetch (session rolled back) and mark as error
            draft2 = self.draft_repo.get_by_id(draft_id)
            if draft2:
                self.draft_repo.set_status(draft2, "error")
                self.db.commit()
            logger.exception("Draft activation failed for %s", draft_id)
            raise RuntimeError(f"Activation failed: {exc}") from exc

    # ─────────────────────────────────────────────────────────────────────────

    def _activate(self, payload: dict) -> int:
        # ── Validate payload via Pydantic ──────────────────────────────────
        data = DraftPayload.model_validate(payload)

        if not data.step1:
            raise ValueError("Step 1 (track basics) is required")

        # ── Step 1: create Track ───────────────────────────────────────────
        s1 = data.step1
        track = self.track_repo.create_track(
            title=s1.title,
            isrc=s1.isrc,
            duration=s1.duration,
            explicit=bool(s1.explicit),
            resource_reference=s1.resource_reference,
            label_own_code=s1.label_own_code,
        )

        if s1.label_id:
            self.track_repo.add_label(track.id, s1.label_id)

        # ── Step 2: release ────────────────────────────────────────────────
        if data.step2:
            s2 = data.step2
            release = None
            if s2.release_id:
                release = self.track_repo.get_release(s2.release_id)
            elif s2.new_release:
                nr = s2.new_release
                release = self.track_repo.create_release(
                    title=nr.title,
                    upc=nr.upc,
                    release_date=nr.release_date,
                    label_id=nr.label_id,
                )
            if release:
                self.track_repo.link_track_release(track, release)

        # ── Step 3: contributors ───────────────────────────────────────────
        if data.step3:
            for c in data.step3.contributors:
                if c.person_id:
                    person = self.person_repo.get_by_id(c.person_id)
                    if person is None:
                        raise ValueError(f"Person {c.person_id} not found")
                else:
                    person = self.person_repo.get_or_create(c.full_name)
                self.track_repo.add_contribution(track.id, person.id, c.role)

        # ── Step 4: rights ─────────────────────────────────────────────────
        if data.step4 and data.step4.rights:
            self._validate_rights_shares(data.step4.rights)
            for r in data.step4.rights:
                self.track_repo.add_right(
                    track_id=track.id,
                    right_holder_id=r.right_holder_id,
                    right_category_id=r.right_category_id,
                    right_usage_type_id=r.right_usage_type_id,
                    share_percentage=decimal.Decimal(str(r.share_percentage)),
                    contract_id=r.contract_id,
                    region_id=r.region_id,
                )

        return track.id

    def _update(self, track_id: int, payload: dict) -> int:
        """Update an existing track in place from draft payload (edit mode)."""
        data = DraftPayload.model_validate(payload)

        if not data.step1:
            raise ValueError("Step 1 (track basics) is required")

        track = self.track_repo.get_track(track_id)
        if track is None:
            raise ValueError(f"Track {track_id} not found")

        # ── Step 1: update Track basics ────────────────────────────────────
        s1 = data.step1
        self.track_repo.update_track(
            track,
            title=s1.title,
            isrc=s1.isrc,
            duration=s1.duration,
            explicit=bool(s1.explicit),
            resource_reference=s1.resource_reference,
            label_own_code=s1.label_own_code,
        )
        self.track_repo.replace_label(track.id, s1.label_id)

        # ── Step 2: release ────────────────────────────────────────────────
        if data.step2:
            s2 = data.step2
            release = None
            if s2.release_id:
                release = self.track_repo.get_release(s2.release_id)
            elif s2.new_release:
                nr = s2.new_release
                release = self.track_repo.create_release(
                    title=nr.title,
                    upc=nr.upc,
                    release_date=nr.release_date,
                    label_id=nr.label_id,
                )
            self.track_repo.replace_release_link(track, release)

        # ── Step 3: contributors (replace all) ─────────────────────────────
        self.track_repo.clear_contributions(track.id)
        if data.step3:
            for c in data.step3.contributors:
                if c.person_id:
                    person = self.person_repo.get_by_id(c.person_id)
                    if person is None:
                        raise ValueError(f"Person {c.person_id} not found")
                else:
                    person = self.person_repo.get_or_create(c.full_name)
                self.track_repo.add_contribution(track.id, person.id, c.role)

        # ── Step 4: rights (replace all) ───────────────────────────────────
        rights = data.step4.rights if data.step4 else []
        if rights:
            self._validate_rights_shares(rights)
        self.track_repo.clear_rights(track.id)
        for r in rights:
            self.track_repo.add_right(
                track_id=track.id,
                right_holder_id=r.right_holder_id,
                right_category_id=r.right_category_id,
                right_usage_type_id=r.right_usage_type_id,
                share_percentage=decimal.Decimal(str(r.share_percentage)),
                contract_id=r.contract_id,
                region_id=r.region_id,
            )

        return track.id

    @staticmethod
    def _validate_rights_shares(rights) -> None:
        """Share percentage is limited to 100% per (right_category_id, right_usage_type_id)
        combination, not across the whole track (a track can have several categories and
        usage types, each capped independently at 100%)."""
        totals: dict[tuple, decimal.Decimal] = {}
        for r in rights:
            key = (r.right_category_id, r.right_usage_type_id)
            totals[key] = totals.get(key, decimal.Decimal(0)) + decimal.Decimal(str(r.share_percentage))
        for (category_id, usage_type_id), total in totals.items():
            if total > 100:
                raise ValueError(
                    f"Сумма долей превышает 100% для категории прав {category_id} "
                    f"и типа использования {usage_type_id} (сумма: {total})"
                )
