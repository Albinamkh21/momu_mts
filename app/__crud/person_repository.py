"""PersonRepository — get or create Person records."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from models import Person
from tasks.report_tasks import _normalize_name


class PersonRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, person_id: int) -> Optional[Person]:
        return self.db.query(Person).filter(Person.id == person_id).first()

    def get_or_create(self, full_name: str) -> Person:
        tokens, norm_key_full = _normalize_name(full_name)
        existing = (
            self.db.query(Person)
            .filter(Person.norm_key_full == norm_key_full)
            .first()
        )
        if existing:
            return existing

        person = Person(
            full_name=full_name,
            norm_key_full=norm_key_full,
            tokens=tokens,
        )
        self.db.add(person)
        self.db.flush()
        return person
