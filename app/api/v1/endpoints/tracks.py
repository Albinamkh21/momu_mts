from fastapi import APIRouter, Depends, Query, Path, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from typing import Optional
from pydantic import BaseModel
import logging

from core.database import SessionLocal
from tasks.report_tasks import _normalize_name
from __crud.track_repository import TrackRepository, TrackHasReportsError

router = APIRouter()
logger = logging.getLogger(__name__)


class PersonUpdate(BaseModel):
    full_name: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/labels")
def get_labels(db: Session = Depends(get_db)):
    rows = db.execute(text("SELECT id, name FROM label ORDER BY name")).fetchall()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/tracks")
def get_tracks(
    title: Optional[str] = Query(None),
    isrc: Optional[str] = Query(None),
    label_own_code: Optional[str] = Query(None),
    label_id: Optional[int] = Query(None),
    query: Optional[str] = Query(None, description="Общий поиск"),
    artist_name: Optional[str] = Query(None, description="Поиск по исполнителю"),
    author_name: Optional[str] = Query(None, description="Поиск по авторам"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0, description="Сколько записей пропустить"),
    db: Session = Depends(get_db),
    response: Response = None,
):
    # JOINs for person/label filters (replaces EXISTS — uses trigram + composite indexes)
    joins = []
    conditions = []
    params = {"lim": limit, "off": offset}

    if query:
        conditions.append("(t.title ILIKE :q OR t.isrc ILIKE :q)")
        params["q"] = f"%{query}%"
    if title:
        conditions.append("t.title ILIKE :title")
        params["title"] = f"%{title}%"
    if isrc:
        conditions.append("t.isrc = :isrc")
        params["isrc"] = isrc
    if label_own_code:
        conditions.append("t.label_own_code = :loc")
        params["loc"] = label_own_code
    if label_id:
        # Simple semi-join via subquery; uses index on track_label(label_id)
        joins.append("""
            JOIN (
                SELECT track_id FROM track_label WHERE label_id = :label_id
            ) lf ON lf.track_id = t.id
        """)
        params["label_id"] = label_id

    if artist_name:
        # Start from person (trigram index on full_name), then look up
        # track_contribution(person_id, role) — avoids full scan of track_contribution
        joins.append("""
            JOIN (
                SELECT DISTINCT tc.track_id
                FROM person p
                JOIN track_contribution tc
                    ON tc.person_id = p.id
                    AND tc.role IN ('artist', 'artist_name', 'track_artist_name')
                WHERE p.full_name ILIKE :artist_name
            ) af ON af.track_id = t.id
        """)
        params["artist_name"] = f"%{artist_name}%"

    if author_name:
        # Same pattern: trigram scan on person → composite index on track_contribution
        joins.append("""
            JOIN (
                SELECT DISTINCT tc.track_id
                FROM person p
                JOIN track_contribution tc
                    ON tc.person_id = p.id
                    AND tc.role IN ('composer', 'lyricist', 'author', 'authors')
                WHERE p.full_name ILIKE :author_name
            ) auf ON auf.track_id = t.id
        """)
        params["author_name"] = f"%{author_name}%"

    join_clause = "\n".join(joins)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Total count before pagination
    total_row = db.execute(
        text(f"""
            SELECT COUNT(*) AS cnt
            FROM track t
            {join_clause}
            {where}
        """),
        params,
    ).fetchone()

    total = int(total_row.cnt) if total_row is not None else 0
    if response is not None:
        response.headers["X-Total-Count"] = str(total)

    tracks_rows = db.execute(
        text(f"""
            SELECT t.id, t.isrc, t.label_own_code, t.title
            FROM track t
            {join_clause}
            {where}
            ORDER BY t.id
            LIMIT :lim OFFSET :off
        """),
        params,
    ).fetchall()

    if not tracks_rows:
        return []

    track_ids = [r.id for r in tracks_rows]

    # Участники (persons) через track_contribution + person
    persons_rows = db.execute(
        text("""
            SELECT tc.track_id, p.id AS person_id, p.full_name, tc.role
            FROM track_contribution tc
            JOIN person p ON p.id = tc.person_id
            WHERE tc.track_id = ANY(:ids)
        """),
        {"ids": track_ids},
    ).fetchall()

    # Лейблы через track_label + label
    labels_rows = db.execute(
        text("""
            SELECT tl.track_id, l.name
            FROM track_label tl
            JOIN label l ON l.id = tl.label_id
            WHERE tl.track_id = ANY(:ids)
        """),
        {"ids": track_ids},
    ).fetchall()

    # Группируем по track_id
    persons_by_track: dict[int, list] = {}
    for r in persons_rows:
        persons_by_track.setdefault(r.track_id, []).append(
            {"id": r.person_id, "name": r.full_name, "role": r.role}
        )

    labels_by_track: dict[int, list] = {}
    for r in labels_rows:
        labels_by_track.setdefault(r.track_id, []).append({"name": r.name})

    return [
        {
            "id": t.id,
            "isrc": t.isrc,
            "label_own_code": t.label_own_code,
            "title": t.title,
            "persons": persons_by_track.get(t.id, []),
            "labels": labels_by_track.get(t.id, []),
        }
        for t in tracks_rows
    ]


@router.get("/tracks/{track_id}")
def get_track_detail(track_id: int = Path(...), db: Session = Depends(get_db)):
    # Основная информация о треке
    row = db.execute(
        text("""
            SELECT t.id, t.isrc, t.label_own_code, t.title,
                   t.explicit, t.resource_reference
            FROM track t
            WHERE t.id = :tid
        """),
        {"tid": track_id},
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Track not found")

    # Релиз
    release = None
    try:
        release_row = db.execute(
            text("""
                SELECT r.id, r.upc, r.title, r.release_date, r.status
                FROM "release" r
                JOIN track t ON t.release_id = r.id
                WHERE t.id = :tid
            """),
            {"tid": track_id},
        ).fetchone()
        if release_row:
            release = {
                "id": release_row.id,
                "upc": release_row.upc,
                "title": release_row.title,
                "release_date": str(release_row.release_date) if release_row.release_date else None,
                "status": release_row.status,
            }
    except Exception as e:
        db.rollback()
        logger.warning("Failed to fetch release for track %s: %s", track_id, e)

    # Лейблы
    labels = []
    try:
        labels_rows = db.execute(
            text("""
                SELECT l.id, l.name
                FROM track_label tl
                JOIN label l ON l.id = tl.label_id
                WHERE tl.track_id = :tid
            """),
            {"tid": track_id},
        ).fetchall()
        labels = [{"id": l.id, "name": l.name} for l in labels_rows]
    except Exception as e:
        db.rollback()
        logger.warning("Failed to fetch labels for track %s: %s", track_id, e)

    # Участники (persons)
    persons = []
    try:
        persons_rows = db.execute(
            text("""
                SELECT p.id, p.full_name, tc.role
                FROM track t
                INNER JOIN track_contribution tc ON t.id = tc.track_id
                INNER JOIN person p ON p.id = tc.person_id
                WHERE t.id = :tid
                ORDER BY tc.role, p.full_name
            """),
            {"tid": track_id},
        ).fetchall()
        persons = [{"id": p.id, "name": p.full_name, "role": p.role} for p in persons_rows]
    except Exception as e:
        db.rollback()
        logger.warning("Failed to fetch persons for track %s: %s", track_id, e)

    # Права (track_right)
    rights_result = []
    try:
        rights = db.execute(
            text("""
                SELECT
                    rh.name AS holder_name,
                    rc.name AS category_name,
                    rut.code AS usage_code,
                    tr.share_percentage
                FROM track_right tr
                LEFT JOIN right_holder rh ON rh.id = tr.right_holder_id
                LEFT JOIN right_category rc ON rc.id = tr.right_category_id
                LEFT JOIN right_usage_type rut ON rut.id = tr.right_usage_type_id
                WHERE tr.track_id = :tid
                ORDER BY rc.name, rh.name, rut.code
            """),
            {"tid": track_id},
        ).fetchall()

        rights_map = {}
        for r in rights:
            cat = r.category_name or "Другое"
            holder = r.holder_name or "Неизвестен"
            code = r.usage_code or ""
            share = float(r.share_percentage) if r.share_percentage is not None else 0

            if cat not in rights_map:
                rights_map[cat] = {}
            if holder not in rights_map[cat]:
                rights_map[cat][holder] = {}
            rights_map[cat][holder][code] = share

        for cat, holders in rights_map.items():
            for holder, codes in holders.items():
                rights_result.append({
                    "category": cat,
                    "holder": holder,
                    "ALL": codes.get("ALL", None),
                    "INT": codes.get("INT", None),
                    "MOB": codes.get("MOB", None),
                    "PUB": codes.get("PUB", None),
                })
    except Exception as e:
        db.rollback()
        logger.warning("Failed to fetch rights for track %s: %s", track_id, e)

    return {
        "id": row.id,
        "isrc": row.isrc,
        "label_own_code": row.label_own_code,
        "title": row.title,
        "explicit": row.explicit,
        "release": release,
        "labels": labels,
        "persons": persons,
        "rights": rights_result,
    }


@router.delete("/tracks/{track_id}")
def delete_track(track_id: int = Path(...), db: Session = Depends(get_db)):
    repo = TrackRepository(db)
    track = repo.get_track(track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")

    person_ids = repo.get_contribution_person_ids(track_id)
    right_holder_ids = repo.get_right_holder_ids(track_id)

    try:
        repo.delete_track(track)
    except TrackHasReportsError:
        db.rollback()
        # Это контролируемый нами случай: у старого трека есть отчеты
        raise HTTPException(
            status_code=409,
            detail="Невозможно удалить трек: на него есть ссылки в отчётах.",
        )
    except IntegrityError as e:
        db.rollback()
        # Это непредвиденная ошибка БД (например, забыли какую-то связь каскадировать)
        raise HTTPException(
            status_code=500,
            detail=f"Системная ошибка при удалении трека: {str(e)}",
        )

    removed_persons = []
    for person_id in person_ids:
        if not repo.person_referenced_elsewhere(person_id):
            repo.delete_person(person_id)
            removed_persons.append(person_id)

    removed_right_holders = []
    for right_holder_id in right_holder_ids:
        if not repo.right_holder_referenced_elsewhere(right_holder_id):
            repo.delete_right_holder(right_holder_id)
            removed_right_holders.append(right_holder_id)

    db.commit()

    return {
        "id": track_id,
        "deleted": True,
        "removed_person_ids": removed_persons,
        "removed_right_holder_ids": removed_right_holders,
    }


@router.post("/persons", status_code=201)
def create_person(body: PersonUpdate, db: Session = Depends(get_db)):
    name = body.full_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="full_name is required")

    existing = db.execute(
        text("SELECT id, full_name FROM person WHERE full_name = :name"),
        {"name": name},
    ).fetchone()
    if existing:
        return {"id": existing.id, "full_name": existing.full_name}

    tokens, norm_key_full = _normalize_name(name)
    result = db.execute(
        text(
            "INSERT INTO person (full_name, norm_key_full, tokens) "
            "VALUES (:name, :norm, :tokens) RETURNING id, full_name"
        ),
        {"name": name, "norm": norm_key_full, "tokens": tokens},
    ).fetchone()
    db.commit()
    return {"id": result.id, "full_name": result.full_name}


@router.get("/persons/{person_id}")
def get_person(person_id: int = Path(...), db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id, full_name FROM person WHERE id = :pid"),
        {"pid": person_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Person not found")

    # Треки этого участника
    tracks = db.execute(
        text("""
            SELECT t.id, t.title, t.isrc, tc.role
            FROM track_contribution tc
            JOIN track t ON t.id = tc.track_id
            WHERE tc.person_id = :pid
            ORDER BY t.title
        """),
        {"pid": person_id},
    ).fetchall()

    return {
        "id": row.id,
        "full_name": row.full_name,
        "tracks": [{"id": t.id, "title": t.title, "isrc": t.isrc, "role": t.role} for t in tracks],
    }


@router.put("/persons/{person_id}")
def update_person_name(
    person_id: int = Path(...),
    body: PersonUpdate = ...,
    db: Session = Depends(get_db),
):
    row = db.execute(
        text("SELECT id FROM person WHERE id = :pid"),
        {"pid": person_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Person not found")

    db.execute(
        text("UPDATE person SET full_name = :name WHERE id = :pid"),
        {"name": body.full_name.strip(), "pid": person_id},
    )
    db.commit()

    return {"id": person_id, "full_name": body.full_name.strip()}
