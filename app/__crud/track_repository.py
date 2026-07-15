"""TrackRepository — create tracks and attach relations."""
from __future__ import annotations

import datetime
import decimal
from typing import Optional

from sqlalchemy.orm import Session

from models import Track, TrackLabel, TrackContribution, TrackRight, Release
from tasks.report_tasks import _normalize_title


class TrackRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Track ────────────────────────────────────────────────────────────────

    def create_track(
        self,
        title: str,
        isrc: Optional[str] = None,
        duration: Optional[str] = None,
        explicit: bool = False,
        resource_reference: Optional[str] = None,
        label_own_code: Optional[str] = None,
    ) -> Track:
        title_tokens, title_norm_key = _normalize_title(title)
        track = Track(
            title=title,
            isrc=isrc,
            duration=duration,
            explicit=explicit,
            resource_reference=resource_reference,
            label_own_code=label_own_code,
            title_tokens=title_tokens or None,
            title_norm_key=title_norm_key or None,
        )
        self.db.add(track)
        self.db.flush()
        return track

    def get_track(self, track_id: int) -> Optional[Track]:
        return self.db.query(Track).filter(Track.id == track_id).first()

    def update_track(
        self,
        track: Track,
        title: str,
        isrc: Optional[str] = None,
        duration: Optional[str] = None,
        explicit: bool = False,
        resource_reference: Optional[str] = None,
        label_own_code: Optional[str] = None,
    ) -> Track:
        title_tokens, title_norm_key = _normalize_title(title)
        track.title = title
        track.isrc = isrc
        track.duration = duration
        track.explicit = explicit
        track.resource_reference = resource_reference
        track.label_own_code = label_own_code
        track.title_tokens = title_tokens or None
        track.title_norm_key = title_norm_key or None
        self.db.flush()
        return track

    # ── Label ────────────────────────────────────────────────────────────────

    def add_label(self, track_id: int, label_id: int) -> TrackLabel:
        tl = TrackLabel(track_id=track_id, label_id=label_id)
        self.db.add(tl)
        self.db.flush()
        return tl

    def replace_label(self, track_id: int, label_id: Optional[int]) -> None:
        """Remove all existing label links for the track and set a single new one."""
        self.db.query(TrackLabel).filter(TrackLabel.track_id == track_id).delete()
        self.db.flush()
        if label_id:
            self.add_label(track_id, label_id)

    # ── Release ──────────────────────────────────────────────────────────────

    def get_release(self, release_id: int) -> Optional[Release]:
        return self.db.query(Release).filter(Release.id == release_id).first()

    def create_release(
        self,
        title: str,
        upc: Optional[str] = None,
        release_date: Optional[str] = None,
        label_id: Optional[int] = None,
    ) -> Release:
        rd = None
        if release_date:
            try:
                rd = datetime.date.fromisoformat(release_date)
            except ValueError:
                pass
        release = Release(title=title, upc=upc, release_date=rd, label_id=label_id)
        self.db.add(release)
        self.db.flush()
        return release

    def link_track_release(self, track: Track, release: Release) -> None:
        if release not in track.release:
            track.release.append(release)
        self.db.flush()

    def replace_release_link(self, track: Track, release: Optional[Release]) -> None:
        """Detach the track from all releases and link it to a single new one (if any)."""
        track.release.clear()
        if release:
            track.release.append(release)
        self.db.flush()

    # ── Contribution ─────────────────────────────────────────────────────────

    def add_contribution(self, track_id: int, person_id: int, role: str) -> TrackContribution:
        existing = (
            self.db.query(TrackContribution)
            .filter_by(track_id=track_id, person_id=person_id, role=role)
            .first()
        )
        if existing:
            return existing
        tc = TrackContribution(track_id=track_id, person_id=person_id, role=role)
        self.db.add(tc)
        self.db.flush()
        return tc

    def clear_contributions(self, track_id: int) -> None:
        self.db.query(TrackContribution).filter(TrackContribution.track_id == track_id).delete()
        self.db.flush()

    # ── Rights ───────────────────────────────────────────────────────────────

    def add_right(
        self,
        track_id: int,
        right_holder_id: int,
        right_category_id: int,
        right_usage_type_id: int,
        share_percentage: decimal.Decimal,
        contract_id: Optional[int] = None,
        region_id: Optional[int] = None,
    ) -> TrackRight:
        tr = TrackRight(
            track_id=track_id,
            right_holder_id=right_holder_id,
            right_category_id=right_category_id,
            right_usage_type_id=right_usage_type_id,
            share_percentage=share_percentage,
            contract_id=contract_id,
            region_id=region_id,
        )
        self.db.add(tr)
        self.db.flush()
        return tr

    def clear_rights(self, track_id: int) -> None:
        self.db.query(TrackRight).filter(TrackRight.track_id == track_id).delete()
        self.db.flush()
