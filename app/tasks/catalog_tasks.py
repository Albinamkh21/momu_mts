import os
import re as _re
import uuid
from datetime import datetime
import time
import polars as pl
from polars import lit
from sqlalchemy import create_engine, text
from core.celery_app import celery_app
from celery import current_task
from .utils import clean_null_bytes
from core.constants import RightCategory, RightUsageType

from services.broadcaster import TaskProgress
from services.csv_writer import BaseCSVWriter, TomeExcelWriter, TomeWriterFactory
import xlsxwriter



DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

@celery_app.task(name="process_catalog_file", bind=True)
def process_catalog_file(self, file_path: str, user_id: str, original_filename: str = ""):
    task_id = self.request.id
    print(f"📂 Task process_catalog_file[{self.request.id}] файл: {original_filename}")
    TaskProgress.emit(task_id, f"📂 Task process_catalog_file[{self.request.id}] файл: {original_filename}")
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File not found"}

    upload_id = str(uuid.uuid4())
    start_time = datetime.now()    

    try:
        with engine.begin() as conn:
            pass
            #conn.execute(text("TRUNCATE TABLE staging_catalog"))

        df = pl.read_excel(file_path, infer_schema_length=0) 
        
        total_rows = len(df)
        chunk_size = 50000

        db_columns = [
            "upc", "isrc", "track_name", "genre_name", "album_name",
            "album_single", "track_number", "artist_name", "track_artist_name",
            "composer", "lyricist", "authors", "explicit", "duration",
            "label_name", "total_author_right", "right_id", "author_right_1",
            "ar_label_treaty_number_1", "author_right_2", "ar_label_treaty_number_2",
            "author_right_3", "ar_label_treaty_number_3", "total_related_right",
            "related_right_id_1", "rr_label_treaty_number_1", "related_right_id_2",
            "rr_label_treaty_number_2", "related_right_id_3", "rr_label_treaty_number_3",
            "types_of_rights", "countries", "create_date", "release_date",
            "sales_start_date", "has_ringtone", "ringtone_upc", "ringtone_isrc",
            "has_vclip", "vclip_isrc", "video_upc", "has_lyrics", "has_ttml",
            "effective_date", "termination_date", "active_inactive", "resource_reference",
            "track_id", "track_song_id"
        ]

        for i in range(0, total_rows, chunk_size):
            chunk = df.slice(i, chunk_size)
            
            chunk.columns = db_columns
            
            chunk = clean_null_bytes(chunk)

            # Обрабатываем поле isrc - берём только первую часть до точки с запятой
            chunk = chunk.with_columns(
                pl.col("isrc")
                .str.split(";")
                .list.first()
                .str.strip_chars()
                .alias("isrc")
            )

            chunk = chunk.with_columns(
                pl.col("explicit")
                .str.to_lowercase()
                .str.strip_chars()
                .is_in(["true", "yes", "1", "explicit", "да"])
                .fill_null(False)
                .cast(pl.String)
                .alias("explicit")
            )

            chunk = chunk.with_columns(
                pl.col("duration").map_elements(
                    lambda x: f"00:{x}" if x and len(x) <= 5 else x,
                    return_dtype=pl.String
                )
            )

            chunk = chunk.with_columns([
                pl.lit(upload_id).alias("upload_id"),
                pl.lit(user_id).alias("user_id"), 
                pl.lit(start_time).alias("created_at")
            ])
            
            chunk.write_database(
                table_name="staging_catalog",
                connection=DATABASE_URL,
                if_table_exists="append",
                engine="adbc"
            )
            print(f"📦 Загружен батч: {i} - {i + len(chunk)}")
            TaskProgress.emit(task_id, f"📦 Загружен батч: {i} - {i + len(chunk)}")

        os.remove(file_path)
        return {"status": "success", "total_rows": total_rows, "upload_id": upload_id}

    except Exception as e:
        print(f"❌ Ошибка воркера: {str(e)}")
        TaskProgress.emit(task_id, f"❌ Ошибка воркера: {str(e)}")
        return {"status": "error", "message": str(e)}



@celery_app.task(name="check_catalog_integrity")
def check_catalog_integrity():
    results = {}
    with engine.connect() as conn:
        # --- 1. LABEL ---
        row = conn.execute(text("""
            SELECT 
                (SELECT COUNT(DISTINCT TRIM(label_name)) FROM staging_catalog 
                    WHERE label_name IS NOT NULL AND TRIM(label_name) != '') AS staging_count,
                (SELECT COUNT(*) FROM label) AS target_count
        """)).fetchone()
        missing_labels = conn.execute(text("""
            SELECT DISTINCT TRIM(label_name) FROM staging_catalog
            WHERE label_name IS NOT NULL AND TRIM(label_name) != ''
            EXCEPT
            SELECT name FROM label
        """)).fetchall()
        results["label"] = {
            "staging_count": row[0],
            "target_count": row[1],
            "missing_count": len(missing_labels),
            "missing": [r[0] for r in missing_labels] if missing_labels else [],
            "ok": len(missing_labels) == 0
        }

        # --- 2. PERSON ---
        row = conn.execute(text("""
            WITH person_names AS (
                SELECT DISTINCT TRIM(unnest(string_to_array(artist_name, ','))) AS name
                FROM staging_catalog WHERE artist_name IS NOT NULL AND artist_name != ''
                UNION
                SELECT DISTINCT TRIM(unnest(string_to_array(track_artist_name, ','))) AS name
                FROM staging_catalog WHERE track_artist_name IS NOT NULL AND track_artist_name != ''
                UNION
                SELECT DISTINCT TRIM(unnest(string_to_array(composer, ','))) AS name
                FROM staging_catalog WHERE composer IS NOT NULL AND composer != ''
                UNION
                SELECT DISTINCT TRIM(unnest(string_to_array(lyricist, ','))) AS name
                FROM staging_catalog WHERE lyricist IS NOT NULL AND lyricist != ''
            )
            SELECT
                (SELECT COUNT(*) FROM person_names) AS staging_count,
                (SELECT COUNT(*) FROM person) AS target_count
        """)).fetchone()
        missing_persons = conn.execute(text("""
            WITH person_names AS (
                SELECT DISTINCT TRIM(unnest(string_to_array(artist_name, ','))) AS name
                FROM staging_catalog WHERE artist_name IS NOT NULL AND artist_name != ''
                UNION
                SELECT DISTINCT TRIM(unnest(string_to_array(track_artist_name, ','))) AS name
                FROM staging_catalog WHERE track_artist_name IS NOT NULL AND track_artist_name != ''
                UNION
                SELECT DISTINCT TRIM(unnest(string_to_array(composer, ','))) AS name
                FROM staging_catalog WHERE composer IS NOT NULL AND composer != ''
                UNION
                SELECT DISTINCT TRIM(unnest(string_to_array(lyricist, ','))) AS name
                FROM staging_catalog WHERE lyricist IS NOT NULL AND lyricist != ''
            )
            SELECT name FROM person_names WHERE name IS NOT NULL AND name != ''
            EXCEPT
            SELECT full_name FROM person
        """)).fetchall()
        results["person"] = {
            "staging_count": row[0],
            "target_count": row[1],
            "missing_count": len(missing_persons),
            "missing": [r[0] for r in missing_persons] if missing_persons else [],
            "ok": len(missing_persons) == 0
        }

        # --- 3. RIGHT_HOLDER ---
        row = conn.execute(text("""
            WITH rh_names AS (
                SELECT DISTINCT TRIM(ar_label_treaty_number_1) AS name FROM staging_catalog WHERE ar_label_treaty_number_1 IS NOT NULL AND TRIM(ar_label_treaty_number_1) != ''
                UNION
                SELECT DISTINCT TRIM(ar_label_treaty_number_2) FROM staging_catalog WHERE ar_label_treaty_number_2 IS NOT NULL AND TRIM(ar_label_treaty_number_2) != ''
                UNION
                SELECT DISTINCT TRIM(ar_label_treaty_number_3) FROM staging_catalog WHERE ar_label_treaty_number_3 IS NOT NULL AND TRIM(ar_label_treaty_number_3) != ''
                UNION
                SELECT DISTINCT TRIM(rr_label_treaty_number_1) FROM staging_catalog WHERE rr_label_treaty_number_1 IS NOT NULL AND TRIM(rr_label_treaty_number_1) != ''
                UNION
                SELECT DISTINCT TRIM(rr_label_treaty_number_2) FROM staging_catalog WHERE rr_label_treaty_number_2 IS NOT NULL AND TRIM(rr_label_treaty_number_2) != ''
                UNION
                SELECT DISTINCT TRIM(rr_label_treaty_number_3) FROM staging_catalog WHERE rr_label_treaty_number_3 IS NOT NULL AND TRIM(rr_label_treaty_number_3) != ''
            )
            SELECT 
                (SELECT COUNT(*) FROM rh_names) AS staging_count,
                (SELECT COUNT(*) FROM right_holder) AS target_count
        """)).fetchone()
        missing_rh = conn.execute(text("""
            WITH rh_names AS (
                SELECT DISTINCT TRIM(ar_label_treaty_number_1) AS name FROM staging_catalog WHERE ar_label_treaty_number_1 IS NOT NULL AND TRIM(ar_label_treaty_number_1) != ''
                UNION
                SELECT DISTINCT TRIM(ar_label_treaty_number_2) FROM staging_catalog WHERE ar_label_treaty_number_2 IS NOT NULL AND TRIM(ar_label_treaty_number_2) != ''
                UNION
                SELECT DISTINCT TRIM(ar_label_treaty_number_3) FROM staging_catalog WHERE ar_label_treaty_number_3 IS NOT NULL AND TRIM(ar_label_treaty_number_3) != ''
                UNION
                SELECT DISTINCT TRIM(rr_label_treaty_number_1) FROM staging_catalog WHERE rr_label_treaty_number_1 IS NOT NULL AND TRIM(rr_label_treaty_number_1) != ''
                UNION
                SELECT DISTINCT TRIM(rr_label_treaty_number_2) FROM staging_catalog WHERE rr_label_treaty_number_2 IS NOT NULL AND TRIM(rr_label_treaty_number_2) != ''
                UNION
                SELECT DISTINCT TRIM(rr_label_treaty_number_3) FROM staging_catalog WHERE rr_label_treaty_number_3 IS NOT NULL AND TRIM(rr_label_treaty_number_3) != ''
            )
            SELECT name FROM rh_names
            EXCEPT
            SELECT name FROM right_holder
        """)).fetchall()
        results["right_holder"] = {
            "staging_count": row[0],
            "target_count": row[1],
            "missing_count": len(missing_rh),
            "missing": [r[0] for r in missing_rh] if missing_rh else [],
            "ok": len(missing_rh) == 0
        }

        # --- 4. RELEASE ---
        row = conn.execute(text("""
            SELECT 
                (SELECT COUNT(DISTINCT TRIM(upc)) FROM staging_catalog 
                    WHERE upc IS NOT NULL AND TRIM(upc) != '') AS staging_count,
                (SELECT COUNT(*) FROM release) AS target_count
        """)).fetchone()
        missing_releases = conn.execute(text("""
            SELECT DISTINCT TRIM(upc) AS upc FROM staging_catalog
            WHERE upc IS NOT NULL AND TRIM(upc) != ''
            EXCEPT
            SELECT upc FROM release WHERE upc IS NOT NULL
        """)).fetchall()
        results["release"] = {
            "staging_count": row[0],
            "target_count": row[1],
            "missing_count": len(missing_releases),
            "missing": [r[0] for r in missing_releases] if missing_releases else [],
            "ok": len(missing_releases) == 0
        }

        # --- 5. TRACK ---
        row = conn.execute(text("""
            SELECT 
                (SELECT COUNT(*) FROM staging_catalog) AS staging_count,
                (SELECT COUNT(*) FROM track) AS target_count
        """)).fetchone()
        missing_tracks = conn.execute(text("""
            SELECT sc.id, TRIM(sc.isrc) AS isrc, TRIM(sc.track_name) AS track_name
            FROM staging_catalog sc
            LEFT JOIN track t ON (
                (NULLIF(TRIM(sc.isrc), '') IS NOT NULL AND t.isrc = TRIM(sc.isrc))
                OR
                (NULLIF(TRIM(sc.isrc), '') IS NULL AND t.title = COALESCE(NULLIF(TRIM(sc.track_name), ''), 'Unknown Track'))
            )
            WHERE t.id IS NULL
            LIMIT 100
        """)).fetchall()
        results["track"] = {
            "staging_count": row[0],
            "target_count": row[1],
            "missing_count": row[0] - row[1] if row[0] > row[1] else 0,
            "missing_sample": [{"staging_id": r[0], "isrc": r[1], "track_name": r[2]} for r in missing_tracks],
            "ok": len(missing_tracks) == 0
        }

        # --- 6. TRACK_CONTRIBUTION ---
        row = conn.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM staging_catalog 
                    WHERE (artist_name IS NOT NULL AND artist_name != '')
                       OR (track_artist_name IS NOT NULL AND track_artist_name != '')
                       OR (composer IS NOT NULL AND composer != '')
                       OR (lyricist IS NOT NULL AND lyricist != '')
                       OR (authors IS NOT NULL AND authors != '')) AS staging_with_contributors,
                (SELECT COUNT(DISTINCT track_id) FROM track_contribution) AS tracks_with_contributions
        """)).fetchone()
        orphan_contributions = conn.execute(text("""
            SELECT sc.id, TRIM(sc.isrc) AS isrc, TRIM(sc.track_name) AS track_name,
                   TRIM(sc.artist_name) AS artist_name, TRIM(sc.composer) AS composer
            From staging_catalog sc
            WHERE (sc.artist_name IS NOT NULL AND sc.artist_name != '')
               OR (sc.composer IS NOT NULL AND sc.composer != '')
               OR (sc.lyricist IS NOT NULL AND sc.lyricist != '')
            EXCEPT
            SELECT DISTINCT sc.id, TRIM(sc.isrc), TRIM(sc.track_name),
                   TRIM(sc.artist_name), TRIM(sc.composer)
            FROM staging_catalog sc
            JOIN track t ON (
                (NULLIF(TRIM(sc.isrc), '') IS NOT NULL AND t.isrc = TRIM(sc.isrc))
                OR
                (NULLIF(TRIM(sc.isrc), '') IS NULL AND t.title = TRIM(sc.track_name))
            )
            JOIN track_contribution tc ON tc.track_id = t.id
            LIMIT 50
        """)).fetchall()
        results["track_contribution"] = {
            "staging_rows_with_contributors": row[0],
            "tracks_with_contributions": row[1],
            "missing_sample_count": len(orphan_contributions),
            "missing_sample": [{"staging_id": r[0], "isrc": r[1], "track_name": r[2]} for r in orphan_contributions],
            "ok": len(orphan_contributions) == 0
        }

        # --- 7. TRACK_RIGHT ---
        row = conn.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM staging_catalog 
                    WHERE (ar_label_treaty_number_1 IS NOT NULL AND TRIM(ar_label_treaty_number_1) != '')
                       OR (ar_label_treaty_number_2 IS NOT NULL AND TRIM(ar_label_treaty_number_2) != '')
                       OR (ar_label_treaty_number_3 IS NOT NULL AND TRIM(ar_label_treaty_number_3) != '')
                       OR (rr_label_treaty_number_1 IS NOT NULL AND TRIM(rr_label_treaty_number_1) != '')
                       OR (rr_label_treaty_number_2 IS NOT NULL AND TRIM(rr_label_treaty_number_2) != '')
                       OR (rr_label_treaty_number_3 IS NOT NULL AND TRIM(rr_label_treaty_number_3) != '')) AS staging_with_rights,
                (SELECT COUNT(*) FROM track_right) AS total_track_rights,
                (SELECT COUNT(DISTINCT track_id) FROM track_right) AS tracks_with_rights
        """)).fetchone()
        results["track_right"] = {
            "staging_rows_with_rights": row[0],
            "total_track_rights": row[1],
            "tracks_with_rights": row[2],
            "ok": row[1] > 0
        }

    return results


import os
import csv
from datetime import datetime
from sqlalchemy import text


def build_standard_query(fields_base: str, group_by: str, extra_where: str = "",
                          label_id: int = None, right_usage_type_id: int = None) -> tuple:
    """Генератор для стандартных плоских запросов (separate_by_rights).
    Работает с track_right, где каждый тип использования - отдельная строка, поэтому
    колонки-пивот (CASE WHEN) и фильтр по right_usage_type_id формируются здесь же.
    fields_base должен содержать плейсхолдер '{columns_sql}' на месте пивот-колонок.
    """
    types_to_process = [
        (RightUsageType.INT, "INT"),
        (RightUsageType.MOB, "MOB"),
        (RightUsageType.PUB, "PUB"),
    ]
    if right_usage_type_id and right_usage_type_id != RightUsageType.ALL:
        if right_usage_type_id == RightUsageType.INT:
            types_to_process = [(RightUsageType.INT, "INT")]
        elif right_usage_type_id == RightUsageType.MOB:
            types_to_process = [(RightUsageType.MOB, "MOB")]
        elif right_usage_type_id == RightUsageType.PUB:
            types_to_process = [(RightUsageType.PUB, "PUB")]

    case_sql = ", ".join([
        f"MAX(CASE WHEN tr.right_usage_type_id = {rut_id} THEN tr.share_percentage ELSE 0 END) AS {label}"
        for rut_id, label in types_to_process
    ])

    where_parts, params = [], {}
    if label_id:
        where_parts.append("m.label_id = :label_id")
        params["label_id"] = label_id
    if right_usage_type_id and right_usage_type_id != RightUsageType.ALL:
        where_parts.append("(tr.right_usage_type_id = :rut_id and share_percentage > 0)")
        params["rut_id"] = right_usage_type_id
    if extra_where:
        where_parts.append(extra_where)

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
        SELECT {fields_base.replace('{columns_sql}', case_sql)}
        FROM 
        mv_track_extended m
        JOIN track_right tr ON tr.track_id = m.track_id
        JOIN right_holder rh ON rh.id = tr.right_holder_id
        JOIN label l ON l.id = rh.label_id
        {where_clause}
        {group_by} 
        ORDER BY m.label_id, m.track_id;
    """
    return query, params

def build_unified_rights_query_old(where_clause: str, right_usage_type_id: int = None) -> str:
    if right_usage_type_id and right_usage_type_id != RightUsageType.ALL:
        suffix = right_usage_type_id.name.lower()
        rel_sql = f"COALESCE(ra.rel_{suffix}, 0) AS related_{suffix}"
        auth_sql = f"COALESCE(ra.auth_{suffix}, 0) AS author_{suffix}"
        filter_sql = f"ra.rel_{suffix} >= 100 AND ra.auth_{suffix} >= 100"
    else:
        rel_sql = "COALESCE(ra.rel_int, 0) AS rel_int, COALESCE(ra.rel_mob, 0) AS rel_mob, COALESCE(ra.rel_pub, 0) AS rel_pub"
        auth_sql = "COALESCE(ra.auth_int, 0) AS auth_int, COALESCE(ra.auth_mob, 0) AS auth_mob, COALESCE(ra.auth_pub, 0) AS auth_pub"
        filter_sql = "(ra.rel_int + ra.rel_mob + ra.rel_pub) >= 300 AND (ra.auth_int + ra.auth_mob + ra.auth_pub) >= 300"

    # Добавляем фильтрацию прав прямо в текущий WHERE
    if where_clause and "WHERE" in where_clause.upper():
        final_where = f"{where_clause} AND {filter_sql}"
    elif where_clause:
        final_where = f"WHERE {where_clause} AND {filter_sql}"
    else:
        final_where = f"WHERE {filter_sql}"

    return f"""
        SELECT 
            m.label_own_code,
            m.upc, m.isrc, m.track_name, m.artist_name,
            m.authors, m.composer, m.lyricist, m.album_name,
            {rel_sql},
            ra.rel_holders AS copyright_holder_related,
            ra.base_code,
            {auth_sql},
            ra.auth_holders AS copyright_holder_author,
            TO_CHAR(m.created_at::timestamp, 'DD-MM-YYYY') AS "Time period"
        FROM mv_track_extended m
        JOIN mv_track_rights ra ON ra.track_id = m.track_id
        {final_where}
        ORDER BY m.label_id, ra.base_code;
    """  
def build_unified_rights_query(label_id: int = None, right_usage_type_id: int = None,
                                is_100plus: bool = True, extra_where: str = "") -> tuple:
    """Генератор для унифицированных запросов (default, 100plus100).
    Работает с mv_track_rights, где каждый тип использования - уже отдельная КОЛОНКА
    (rel_int/rel_mob/rel_pub, auth_int/auth_mob/auth_pub), а не строка, как в track_right.
    Поэтому фильтр по right_usage_type_id здесь не нужен/невозможен - вместо этого
    выбираются нужные колонки, а фильтрация 100+ идёт по их значениям.
    """
    if right_usage_type_id and right_usage_type_id != RightUsageType.ALL:
        if right_usage_type_id == RightUsageType.INT:
            suffix = "int"
        elif right_usage_type_id == RightUsageType.MOB:
            suffix = "mob"
        elif right_usage_type_id == RightUsageType.PUB:
            suffix = "pub"

        rel_sql = f"COALESCE(tr.rel_{suffix}, 0) AS related_{suffix}"
        auth_sql = f"COALESCE(tr.auth_{suffix}, 0) AS author_{suffix}"
        # Фильтр применяется только если is_100plus=True
        filter_sql = f"tr.rel_{suffix} >= 100 AND tr.auth_{suffix} >= 100" if is_100plus else ""
    else:
        rel_sql = "COALESCE(tr.rel_int, 0) AS rel_int, COALESCE(tr.rel_mob, 0) AS rel_mob, COALESCE(tr.rel_pub, 0) AS rel_pub"
        auth_sql = "COALESCE(tr.auth_int, 0) AS auth_int, COALESCE(tr.auth_mob, 0) AS auth_mob, COALESCE(tr.auth_pub, 0) AS auth_pub"
        # Фильтр применяется только если is_100plus=True
        filter_sql = "(tr.rel_int + tr.rel_mob + tr.rel_pub) >= 300 AND (tr.auth_int + tr.auth_mob + tr.auth_pub) >= 300" if is_100plus else ""

    where_parts, params = [], {}
    if label_id:
        where_parts.append("m.label_id = :label_id")
        params["label_id"] = label_id
    if filter_sql:
        where_parts.append(filter_sql)
    if extra_where:
        where_parts.append(extra_where)

    final_where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
        SELECT 
            m.label_own_code,
            m.upc, m.isrc, m.track_name, m.artist_name,
            m.authors, m.composer, m.lyricist, m.album_name,
            {rel_sql},
            tr.rel_holders AS copyright_holder_related,
            tr.base_code,
            {auth_sql},
            tr.auth_holders AS copyright_holder_author,
            TO_CHAR(m.created_at::timestamp, 'DD-MM-YYYY') AS "Time period"
        FROM mv_track_extended m
        JOIN mv_track_rights tr ON tr.track_id = m.track_id
        {final_where}
        ORDER BY m.label_id, tr.base_code;
    """
    return query, params
@celery_app.task(name="export_normalized_catalog_to_flat", bind=True)
def export_normalized_catalog_to_flat(self, output_path: str = None, label_id: int = None, right_usage_type_id: int = None, export_format: str = "default"):
    task_id = self.request.id

    if not export_format:
        export_format = "default"
    if not right_usage_type_id:
        right_usage_type_id = RightUsageType.ALL
    TaskProgress.emit(task_id, f"✅ Начало выгрузки ({export_format}).")
    print(f"✅ Начало выгрузки ({export_format}) - right_usage_type_id {right_usage_type_id}; label_id: {label_id}")

    # Списки колонок для separate_by_rights. Плейсхолдер {columns_sql} заменяется на CASE WHEN
    # пивот-колонки внутри build_standard_query (только там нужен пивот, т.к. только там строки track_right).
    # Форматы default/100plus100 используют build_unified_rights_query, которая сама формирует
    # свои колонки из mv_track_rights (там типы использования - уже колонки, а не строки).
    fields_related = """  m.label_own_code , m.upc, m.isrc, m.track_name, m.artist_name,  m.authors, m.composer, m.lyricist, m.album_name,
           {columns_sql},
            l.name AS copyright_holder """

    fields_author = """ m.track_id, m.label_own_code, m.track_name, m.artist_name,  m.authors, m.composer, m.lyricist, 
           {columns_sql},
            l.name AS copyright_holder """

    fields_factory = {
        "separate_by_rights": {
            "_author": fields_author,
            "_related": fields_related
        }
    }

    group_clause = {
        "separate_by_rights": " GROUP BY  m.track_id, m.label_own_code, m.upc, m.isrc, m.track_name, m.artist_name,  m.authors, m.composer, m.lyricist, m.album_name, l.name, m.label_id ",
    }

    # Конфигурация проходов и суффиксов для полей
    if export_format == "separate_by_rights":
        passes = [
            {"suffix": "_author", "field_key": "_author", "cat_id": RightCategory.AUTHOR, "msg": "авторские"},
            {"suffix": "_related", "field_key": "_related", "cat_id": RightCategory.RELATED, "msg": "смежные"}
        ]
    else:
        passes = [{"suffix": "", "field_key": "default", "cat_id": None, "msg": "все"}]

    storage_dir = output_path or "/app/storage"
    os.makedirs(storage_dir, exist_ok=True)
    total_rows = 0
    CHUNK_SIZE = 100000


    # 3. Выполнение и запись
    try:
        with engine.connect() as conn:
            for p in passes:
                # Дополнительный фильтр по категории прав (только для раздельного прохода separate_by_rights)
                extra_where = ""
                extra_params = {}
                if p["cat_id"] is not None:
                    TaskProgress.emit(task_id, f"⏳ Запуск прохода: {p['msg']} права...")
                    extra_where = "(tr.right_category_id = :cat_id and share_percentage > 0)"
                    extra_params["cat_id"] = p["cat_id"]

                # Формирование колонок и фильтров по label_id/right_usage_type_id инкапсулировано
                # в build_standard_query/build_unified_rights_query - у них разные исходные таблицы
                # (track_right - строки на тип использования, mv_track_rights - уже колонки).
                if export_format == "default":
                    # Для default используем единый запрос без фильтра 100%
                    query, params = build_unified_rights_query(
                        label_id=label_id, right_usage_type_id=right_usage_type_id,
                        is_100plus=False, extra_where=extra_where
                    )

                elif export_format == "100plus100":
                    # Для 100plus100 используем тот же запрос, но с фильтром 100%
                    query, params = build_unified_rights_query(
                        label_id=label_id, right_usage_type_id=right_usage_type_id,
                        is_100plus=True, extra_where=extra_where
                    )

                elif export_format == "separate_by_rights":
                    # Для раздельных файлов оставляем классический плоский запрос с группировкой
                    current_fields = fields_factory["separate_by_rights"][p["field_key"]]
                    query, params = build_standard_query(
                        current_fields, group_clause["separate_by_rights"], extra_where=extra_where,
                        label_id=label_id, right_usage_type_id=right_usage_type_id
                    )

                params.update(extra_params)

                base_filename = f"catalog_{export_format}_{p['suffix']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                # Выполнение запроса
                result = conn.execution_options(stream_results=True).execute(text(query), params)
                TaskProgress.emit(task_id, f"✅ Запрос выполнен для прохода: {p['msg']} права. Начинаем выгрузку в файл...")
                print(f"✅ Запрос выполнен для прохода: {p['msg']} права. Начинаем выгрузку в файл...")

                headers = result.keys()

                #full_writer = BaseCSVWriter(os.path.join(storage_dir, f"{base_filename}_full.csv"), headers)
                tome_writer = TomeWriterFactory.create("xlsx", base_filename, storage_dir, headers, max_rows=CHUNK_SIZE * 5)
                 


                while True:
                    chunk = result.fetchmany(CHUNK_SIZE)
                    if not chunk: 
                        break
                    
                    #full_writer.write_rows(chunk)
                    tome_writer.write_rows(chunk)
                    
                    total_rows += len(chunk)
                    if total_rows % 50000 == 0:
                        TaskProgress.emit(task_id, f"⏳ Выгружено {total_rows} строк...")

                #full_writer.close()
                tome_writer.close()

        if total_rows == 0:
            return {"status": "success", "message": "Нет данных"}

        TaskProgress.emit(task_id, f"✅ Успешно: {total_rows} строк.")
        return {"status": "success", "rows_exported": total_rows}

    except Exception as e:
        TaskProgress.emit(task_id, f"❌ Ошибка: {e}", level="error")
        return {"status": "error", "message": str(e)}






@celery_app.task(name="delete_data_from_all_dictionaries_by_label", bind=True)
def delete_data_from_all_dictionaries_by_label(self, label_id: int):
    """
    Удаляет все данные о треках, связях и правах, привязанных к указанному лейблу.
    Базовые справочники (label,  right_category,
    right_usage_type, finding_source, partners, contract) остаются нетронутыми.
    """
    try:
        task_id = self.request.id
        with engine.begin() as conn:
            # 1. Находим все track_id, привязанные к лейблу
            track_ids_result = conn.execute(text("""
                SELECT track_id FROM track_label WHERE label_id = :label_id
            """), {"label_id": label_id})
            track_ids = [row[0] for row in track_ids_result.fetchall()]

            if not track_ids:
                TaskProgress.emit(task_id, f"🗑️ Нет треков для данного лейбла")
                return {"status": "success", "label_id": label_id, "message": "Нет треков для данного лейбла", "deleted": {}}
  

            print(f"🗑️ Найдено треков для удаления: {len(track_ids)}")
            TaskProgress.emit(task_id, f"🗑️ Найдено треков для удаления: {len(track_ids)}")


            # 6. Удаляем track_label (все связи этих треков, не только текущий лейбл)
            r_track_label = conn.execute(text("""
                DELETE FROM track_label WHERE track_id = ANY(:ids)  and label_id = :label_id
            """), {"ids": track_ids, "label_id": label_id})
            print(f"✅ track_label удалено: {r_track_label.rowcount}")
            TaskProgress.emit(task_id, f"✅ track_label удалено: {r_track_label.rowcount}")

            
            # 3. Определяем, какие треки остались без лейблов (осиротели)
            remaining_tracks = conn.execute(text("""
                SELECT DISTINCT track_id FROM track_label WHERE track_id = ANY(:ids)
            """), {"ids": track_ids}).fetchall()
            remaining_track_ids = {row[0] for row in remaining_tracks}

            orphan_track_ids = [tid for tid in track_ids if tid not in remaining_track_ids]
            TaskProgress.emit(task_id, f"✅ Найдено осиротевших треков: {len(orphan_track_ids)}")


            # 2. Удаляем report (нет ON DELETE CASCADE)
            r_report = conn.execute(text("""
                DELETE FROM report_track_rights_cache WHERE track_id = ANY(:ids)
            """), {"ids": orphan_track_ids})
            print(f"✅ report удалено: {r_report.rowcount}")
            TaskProgress.emit(task_id, f"✅ report удалено: {r_report.rowcount}")

            # 3. Удаляем track_right
            r_track_right = conn.execute(text("""
                DELETE FROM track_right WHERE track_id = ANY(:ids) and right_holder_id IN (select id from right_holder where label_id = :label_id)
                
            """), {"ids": orphan_track_ids, "label_id": label_id})
            print(f"✅ track_right удалено: {r_track_right.rowcount}")
            TaskProgress.emit(task_id, f"✅ track_right удалено: {r_track_right.rowcount}")

            # 4. Удаляем track_contribution
            r_track_contribution = conn.execute(text("""
                DELETE FROM track_contribution WHERE track_id = ANY(:ids) 
            """), {"ids": orphan_track_ids})
            print(f"✅ track_contribution удалено: {r_track_contribution.rowcount}")
            TaskProgress.emit(task_id, f"✅ track_contribution удалено: {r_track_contribution.rowcount}")

            # 5. Удаляем track_release
            r_track_release = conn.execute(text("""
                DELETE FROM track_release WHERE track_id = ANY(:ids)
            """), {"ids": orphan_track_ids})
            print(f"✅ track_release удалено: {r_track_release.rowcount}")
            TaskProgress.emit(task_id, f"✅ track_release удалено: {r_track_release.rowcount}")

        

            # 7. Удаляем сами треки
            r_tracks = conn.execute(text("""
                DELETE FROM track WHERE id = ANY(:ids)
            """), {"ids": orphan_track_ids})
            print(f"✅ track удалено: {r_tracks.rowcount}")
            TaskProgress.emit(task_id, f"✅ track удалено: {r_tracks.rowcount}")

            # 8. Удаляем осиротевшие релизы (без треков)
            r_releases = conn.execute(text("""
                DELETE FROM release r
                WHERE r.label_id = :label_id
                AND NOT EXISTS (
                    SELECT 1 FROM track_release tr WHERE tr.release_id = r.id
                )
            """), {"label_id": label_id})
            print(f"✅ release (осиротевших) удалено: {r_releases.rowcount}")
            TaskProgress.emit(task_id, f"✅ release (осиротевших) удалено: {r_releases.rowcount}")

            # 9. Удаляем осиротевших артистов (у которых больше нет контрибьюций)
            r_persons = conn.execute(text("""
                DELETE FROM person p
                WHERE NOT EXISTS (
                    SELECT 1 FROM track_contribution tc WHERE tc.person_id = p.id 
                )
            """))
            print(f"✅ person (осиротевших) удалено: {r_persons.rowcount}")
            TaskProgress.emit(task_id, f"✅ person (осиротевших) удалено: {r_persons.rowcount}")

            r_right_holders = conn.execute(text("""
                DELETE FROM right_holder rh
                WHERE NOT EXISTS (SELECT 1 FROM track_right tr WHERE tr.right_holder_id = rh.id)
            """))
            print(f"✅ right_holder (осиротевших) удалено: {r_right_holders.rowcount}")
            TaskProgress.emit(task_id, f"✅ right_holder (осиротевших) удалено: {r_right_holders.rowcount}")

            stats = {
                "tracks": r_tracks.rowcount,
                "reports": r_report.rowcount,
                "track_rights": r_track_right.rowcount,
                "track_contributions": r_track_contribution.rowcount,
                "track_releases": r_track_release.rowcount,
                "track_labels": r_track_label.rowcount,
                "releases": r_releases.rowcount,
                "persons": r_persons.rowcount

            }

        with engine.begin() as conn:
            #обновляем материализованное представление, чтобы не было рассинхрона
           TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Начинаем обновление представлений.") 
           conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_extended; "))
           conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights_prev; "))
           conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights; "))
           print(f"🏁 Представления обновлены.")
           TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Представления обновлены.")


        print(f"🏁 Удаление по лейблу {label_id} завершено: {stats}")
        TaskProgress.emit(task_id, f"🏁 Удаление по лейблу {label_id} завершено: {stats}")
        return {"status": "success", "label_id": label_id, "deleted": stats}

    except Exception as e:
        print(f"❌ Ошибка удаления по лейблу: {e}")
        TaskProgress.emit(task_id, f"❌ Ошибка удаления по лейблу: {e}")
        return {"status": "error", "message": str(e)}


