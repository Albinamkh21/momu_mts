from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from pydantic import BaseModel
import logging

from core.database import SessionLocal

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
    author_name: Optional[str] = Query(None, description="Поиск по авторам "),

    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
   
    conditions = []
    params = {"lim": limit}

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
        params["loc"] = f"{label_own_code}"
    if label_id:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM track_label tl 
                WHERE tl.track_id = t.id AND tl.label_id = :label_id
            )
        """)
        params["label_id"] = label_id

    # Для artist_name:
    if artist_name:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM track_contribution tc
                JOIN person p ON p.id = tc.person_id
                WHERE tc.track_id = t.id 
                AND tc.role IN ('artist', 'artist_name', 'track_artist_name') -- Расширяем список
                AND p.full_name ILIKE :artist_name
            )
        """)
        params["artist_name"] = f"%{artist_name}%"

    # Для author_name:
    if author_name:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM track_contribution tc
                JOIN person p ON p.id = tc.person_id
                WHERE tc.track_id = t.id 
                AND tc.role IN ('composer', 'lyricist', 'author', 'authors') -- Добавляем 'authors'
                AND p.full_name ILIKE :author_name
            )
        """)
        params["author_name"] = f"%{author_name}%"    

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    tracks_rows = db.execute(
        text(f"""
            SELECT t.id, t.isrc, t.label_own_code, t.title
            FROM track t
            {where}
            ORDER BY t.id
            LIMIT :lim
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
