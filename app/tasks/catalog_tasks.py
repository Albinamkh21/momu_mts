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

from services.broadcaster import TaskProgress



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



@celery_app.task(name="export_normalized_catalog_to_flat", bind=True)
def export_normalized_catalog_to_flat(self, output_path: str = None, label_id: int = None):

    task_id = self.request.id
    TaskProgress.emit(task_id, f"✅Выгрузка каталога: {output_path}")
    print(f"DEBUG: Task started task_id={task_id}, label_id={label_id}, type={type(label_id)}")
    TaskProgress.emit(task_id, f"DEBUG: Task started task_id={task_id}, label_id={label_id}, type={type(label_id)}")

    # Условие фильтрации по лейблу
    where_clause = "WHERE tl.label_id = :label_id" if label_id else "LIMIT 50"
    
    # Один мощный SQL запрос, который собирает всё в нужном плоском формате
    query = f"""
        WITH authors_flat AS (
            SELECT 
                tc.track_id,
                string_agg(DISTINCT p.full_name, ', ') FILTER (WHERE tc.role = 'artist_name') AS artist_name,
                string_agg(DISTINCT p.full_name, ', ') FILTER (WHERE tc.role = 'track_artist_name') AS track_artist_name,
                string_agg(DISTINCT p.full_name, ', ') FILTER (WHERE tc.role = 'composer') AS composer,
                string_agg(DISTINCT p.full_name, ', ') FILTER (WHERE tc.role = 'lyricist') AS lyricist,
                string_agg(DISTINCT p.full_name, ', ') FILTER (WHERE tc.role = 'authors') AS authors
            FROM track_contribution tc
            JOIN person p ON p.id = tc.person_id
            GROUP BY tc.track_id
        ),
        rights_flat AS (
            SELECT 
                tr.track_id,
                -- Авторские права
                MAX(rh.name) FILTER (WHERE rc.name = 'Author') AS ar_label_treaty_number,
                SUM(tr.share_percentage) FILTER (WHERE rc.name = 'Author' AND rut.code = 'INT') AS author_right_INT,
                SUM(tr.share_percentage) FILTER (WHERE rc.name = 'Author' AND rut.code = 'MOB') AS author_right_MOB,
                SUM(tr.share_percentage) FILTER (WHERE rc.name = 'Author' AND rut.code = 'PUB') AS author_right_PUB,
                -- Смежные права
                MAX(rh.name) FILTER (WHERE rc.name = 'Related') AS rr_label_treaty_number,
                SUM(tr.share_percentage) FILTER (WHERE rc.name = 'Related' AND rut.code = 'INT') AS related_right_id_INT,
                SUM(tr.share_percentage) FILTER (WHERE rc.name = 'Related' AND rut.code = 'MOB') AS related_right_id_MOB,
                SUM(tr.share_percentage) FILTER (WHERE rc.name = 'Related' AND rut.code = 'PUB') AS related_right_id_PUB
            FROM track_right tr
            JOIN right_category rc ON rc.id = tr.right_category_id
            JOIN right_usage_type rut ON rut.id = tr.right_usage_type_id
            JOIN right_holder rh ON rh.id = tr.right_holder_id
            GROUP BY tr.track_id
        )
        SELECT DISTINCT ON (t.id)
            COALESCE(r.upc, '')::TEXT AS upc,
            t.isrc::TEXT, 
            t.title::TEXT AS track_name,
            (t.meta->>'genre')::TEXT AS genre_name,
            COALESCE(r.title, '')::TEXT AS album_name,
           
            (t.meta->>'track_number')::TEXT AS track_number,
            af.artist_name,
            af.track_artist_name,
            af.composer,
            af.lyricist,
            af.authors,
            CASE WHEN t.explicit THEN 'Да' ELSE 'Нет' END AS explicit,
            to_char(t.duration, 'MI:SS') AS duration,
            COALESCE(l.name, '')::TEXT AS label_name,
            t.label_own_code::TEXT AS right_id,
            -- Колонки прав (Author)
            COALESCE(rf.author_right_INT, 0)::TEXT AS author_right_INT,
            COALESCE(rf.author_right_MOB, 0)::TEXT AS author_right_MOB,
            COALESCE(rf.author_right_PUB, 0)::TEXT AS author_right_PUB,
            COALESCE(rf.ar_label_treaty_number, '')::TEXT AS ar_label_treaty_number,
            -- Колонки прав (Related)
            COALESCE(rf.related_right_id_INT, 0)::TEXT AS related_right_id_INT,
            COALESCE(rf.related_right_id_MOB, 0)::TEXT AS related_right_id_MOB,
            COALESCE(rf.related_right_id_PUB, 0)::TEXT AS related_right_id_PUB,
            COALESCE(rf.rr_label_treaty_number, '')::TEXT AS rr_label_treaty_number
           
        FROM track t
        LEFT JOIN authors_flat af ON af.track_id = t.id
        LEFT JOIN rights_flat rf ON rf.track_id = t.id
        LEFT JOIN track_release tr ON tr.track_id = t.id  
        LEFT JOIN release r ON r.id = tr.release_id
        LEFT JOIN track_label tl ON tl.track_id = t.id
        LEFT JOIN label l ON l.id = tl.label_id
        {where_clause} 
        ORDER BY t.id;
    """

    try:
        with engine.connect() as conn:
            if label_id:
                stmt = text(query).params(label_id=label_id)
            else:
                stmt = text(query)
            
            df = pl.read_database(query=stmt, connection=conn, infer_schema_length=None)

        if df.is_empty():
            TaskProgress.emit(task_id, "❌ Нет данных для выгрузки", level="error")
            return {"status": "error", "message": "Нет данных для выгрузки"}


        target_columns = [
            "upc", "isrc", "track_name", "genre_name", "album_name",
            "track_number", "artist_name", "track_artist_name",
            "composer", "lyricist", "authors", "explicit", "duration",
            "label_name", "right_id", 
            "author_right_int", "author_right_mob", "author_right_pub", "ar_label_treaty_number",
            "related_right_id_int", "related_right_id_mob", "related_right_id_pub", "rr_label_treaty_number"
       
        ]
        
     
        df = df.select(target_columns).fill_null("")

        # Путь сохранения
        storage_dir = output_path or "/app/storage"
        os.makedirs(storage_dir, exist_ok=True)
        
        # Формируем имя файла
        filename = f"catalog_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        full_path = os.path.join(storage_dir, filename)

        TaskProgress.emit(task_id, f"✅Данные собраны: {len(df)} строк. Начинаем сохранение...")
        df.write_excel(full_path)
        TaskProgress.emit(task_id, f"✅Файл сохранён: {full_path}")
        return {"status": "success", "rows_exported": len(df), "path": full_path}

    except Exception as e:
        print(f"❌ Ошибка экспорта: {e}")
        TaskProgress.emit(task_id, f"❌ Ошибка экспорта: {e}")
        return {"status": "error", "message": str(e)}



@celery_app.task(name="delete_data_from_all_dictionaries_by_label", bind=True)
def delete_data_from_all_dictionaries_by_label(self, label_id: int):
    """
    Удаляет все данные о треках, связях и правах, привязанных к указанному лейблу.
    Базовые справочники (label, person, right_holder, right_category,
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
                DELETE FROM report WHERE track_id = ANY(:ids)
            """), {"ids": orphan_track_ids})
            print(f"✅ report удалено: {r_report.rowcount}")
            TaskProgress.emit(task_id, f"✅ report удалено: {r_report.rowcount}")

            # 3. Удаляем track_right
            r_track_right = conn.execute(text("""
                DELETE FROM track_right WHERE track_id = ANY(:ids) and right_holder_id IN (select id from right_holder where label_id = :label_id)
                
            """), {"ids": track_ids, "label_id": label_id})
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

            print(f"🏁 Удаление по лейблу {label_id} завершено: {stats}")
            TaskProgress.emit(task_id, f"🏁 Удаление по лейблу {label_id} завершено: {stats}")
            return {"status": "success", "label_id": label_id, "deleted": stats}

    except Exception as e:
        print(f"❌ Ошибка удаления по лейблу: {e}")
        TaskProgress.emit(task_id, f"❌ Ошибка удаления по лейблу: {e}")
        return {"status": "error", "message": str(e)}


