import os
import uuid
from datetime import datetime
import time
import polars as pl
from polars import lit
from sqlalchemy import create_engine, text
from core.celery_app import celery_app
from .utils import clean_null_bytes
from celery import current_task
from services.broadcaster import TaskProgress
import uuid
from datetime import datetime


DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)


# ===========================================================================
#  TASK 1: Загрузка файла в staging_catalog_v2
# ===========================================================================

@celery_app.task(name="process_catalog_file_v2", bind=True)
def process_catalog_file_v2(self, file_path: str, user_id: str, original_filename: str = ""):
    task_id = self.request.id
    print(f"📂 Task process_catalog_file_v2[{self.request.id}] файл: {original_filename}")
    TaskProgress.emit(task_id, f"📂 Task process_catalog_file_v2[{self.request.id}] файл: {original_filename}")
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File not found"}

    upload_id = str(uuid.uuid4())
    start_time = datetime.now()    
    success = False
    try:
        with engine.begin() as conn:
            pass  # Можно добавить логику инициализации

        df = pl.read_excel(file_path,infer_schema_length=0) 
        total_rows = len(df)
        chunk_size = 50000

        db_columns = [
            "track_id", "track_song_id",
            "upc", "isrc", "track_name", "genre_name", "album_name",
            "album_single", "track_number", "artist_name", "track_artist_name",
            "composer", "lyricist", "authors", "explicit", "duration",
            "label_name", "right_id",
            "author_right_int", "author_right_mob", "author_right_pub", "ar_label_treaty_number",
            "related_right_id_int", "related_right_id_mob", "related_right_id_pub", "rr_label_treaty_number",
            "types_of_rights", "countries", "create_date", "release_date",
            "sales_start_date", "has_ringtone", "ringtone_upc", "ringtone_isrc",
            "has_vclip", "vclip_isrc", "video_upc", "has_lyrics", "has_ttml",
            "effective_date", "termination_date", "active_inactive", "resource_reference"
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
                .cast(pl.String)
                .alias("explicit")
            )

        

            chunk = chunk.with_columns([
                pl.lit(upload_id).alias("upload_id"),
                pl.lit(user_id).alias("user_id"), 
                pl.lit(start_time).alias("created_at")
            ])
            chunk.write_database(
                table_name="staging_catalog_v2",
                connection=DATABASE_URL,
                if_table_exists="append",
                engine="adbc"
            )
            print(f"[v2] 📦 Загружен батч: {i} - {i + len(chunk)}")
            TaskProgress.emit(task_id, f"[v2] 📦 Загружен батч: {i} - {i + len(chunk)}")

        os.remove(file_path)
        success = True
        return {"status": "success", "total_rows": total_rows, "upload_id": upload_id}

    except Exception as e:
        print(f"[v2] ❌ Ошибка воркера: {str(e)}")
        TaskProgress.emit(task_id, f"[v2] ❌ Ошибка воркера: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        # Если произошла ошибка (success == False), очищаем staging для этого upload_id
        if not success:
            with engine.begin() as clean_conn:
                clean_conn.execute(
                    text("DELETE FROM staging_catalog_v2 WHERE upload_id = :uid"),
                    {"uid": upload_id}
                )
                clean_conn.execute(
                    text("DELETE FROM staging_person WHERE upload_id = :uid"),
                    {"uid": upload_id}
                )
            TaskProgress.emit(task_id, "🧹 Staging очищен после ошибки в process_catalog_file_v2")    


# ===========================================================================
#  Вспомогательные функции для каждого этапа синхронизации
# ===========================================================================

def _sync_labels_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """1. ЗАПОЛНЯЕМ LABEL"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result_labels = conn.execute(
        text(f"""
        INSERT INTO label (name) 
        SELECT DISTINCT s.label_name
        FROM {staging_table} s
        WHERE s.label_name IS NOT NULL 
        AND s.label_name != ''
        AND s.upload_id = :upload_id
        AND NOT EXISTS (
             SELECT 1 FROM label l 
             WHERE l.name = s.label_name
         )
        RETURNING id;
        """), {"upload_id": upload_id}
    )
    count = result_labels.rowcount
    elapsed = time.time() - t0
    print(f"✅ Labels вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"✅ Labels вставлено: {count} ({elapsed:.1f} сек)")
    return count


def _sync_persons_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """2. ЗАПОЛНЯЕМ STAGING_PERSON (из 5-ти колонок)"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result_persons = conn.execute(
        text(f"""
        WITH person_names AS (
            SELECT id AS staging_id, TRIM(unnest(clean_and_split_person_names(artist_name))) AS name, 'artist_name' AS role 
            FROM {staging_table} WHERE artist_name IS NOT NULL AND artist_name != '' AND upload_id = :upload_id
            UNION ALL
            SELECT id AS staging_id, TRIM(unnest(clean_and_split_person_names(track_artist_name))) AS name, 'track_artist_name' AS role 
            FROM {staging_table} WHERE track_artist_name IS NOT NULL AND track_artist_name != '' AND upload_id = :upload_id
            UNION ALL
            SELECT id AS staging_id, TRIM(unnest(clean_and_split_person_names(composer))) AS name, 'composer' AS role 
            FROM {staging_table} WHERE composer IS NOT NULL AND composer != '' AND upload_id = :upload_id
            UNION ALL
            SELECT id AS staging_id, TRIM(unnest(clean_and_split_person_names(lyricist))) AS name, 'lyricist' AS role 
            FROM {staging_table} WHERE lyricist IS NOT NULL AND lyricist != '' AND upload_id = :upload_id
            UNION ALL
            SELECT id AS staging_id, TRIM(unnest(clean_and_split_person_names(authors))) AS name, 'authors' AS role 
            FROM {staging_table} WHERE authors IS NOT NULL AND authors != '' AND upload_id = :upload_id
        )
        INSERT INTO staging_person (staging_id, full_name, upload_id, role)
        SELECT DISTINCT staging_id, name, :upload_id, role
        FROM person_names 
        WHERE name IS NOT NULL AND name != ''
        """), {"upload_id": upload_id}
    )
    count = result_persons.rowcount
    elapsed = time.time() - t0
    print(f"✅ Staging persons вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"✅ Staging persons вставлено: {count} ({elapsed:.1f} сек)")
    return count



def _insert_unique_persons_v2(conn, upload_id):
    """2.2 ВСТАВЛЯЕМ УНИКАЛЬНЫХ ПЕРСОН В PERSON из staging_person по full_name_norm_key"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result = conn.execute(
        text("""
        INSERT INTO person (full_name, tokens, norm_key_full)
        SELECT DISTINCT ON (sp.full_name_norm_key)
        sp.full_name, sp.tokens, sp.full_name_norm_key
        FROM staging_person sp
        WHERE sp.upload_id = :upload_id
        AND sp.full_name_norm_key IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM person p WHERE p.norm_key_full = sp.full_name_norm_key
        )
        ORDER BY sp.full_name_norm_key, sp.full_name
        ON CONFLICT (norm_key_full) DO NOTHING
        """), {"upload_id": upload_id}
    )
    count = result.rowcount
    elapsed = time.time() - t0
    print(f"✅ Unique persons вставлено в person: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"✅ Unique persons вставлено в person: {count} ({elapsed:.1f} сек)")
    return count


def _sync_right_holders_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """3. ЗАПОЛНЯЕМ RIGHT_HOLDER"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result_rights = conn.execute(
        text(f"""
        WITH right_holder_names AS (
            SELECT DISTINCT 
                ar_label_treaty_number AS name,
                label_name,
                effective_date,
                termination_date
            FROM {staging_table} 
            WHERE ar_label_treaty_number IS NOT NULL AND ar_label_treaty_number != '' AND upload_id = :upload_id
            
            UNION
            
            SELECT DISTINCT 
                rr_label_treaty_number AS name,
                label_name,
                effective_date,
                termination_date
            FROM {staging_table} 
            WHERE rr_label_treaty_number IS NOT NULL AND rr_label_treaty_number != '' AND upload_id = :upload_id
        ),
        deduped AS (
            SELECT DISTINCT ON (name)
                name, label_name, effective_date, termination_date
            FROM right_holder_names
            ORDER BY name, effective_date NULLS LAST, termination_date NULLS LAST
        )
        INSERT INTO right_holder (name, label_id, effective_date, termination_date)
        SELECT 
            d.name,
            l.id,
            CASE
                WHEN d.effective_date ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' THEN CAST(d.effective_date AS DATE)
                WHEN d.effective_date ~ '^[0-9]{{2}}\.[0-9]{{2}}\.[0-9]{{4}}$' THEN TO_DATE(d.effective_date, 'DD.MM.YYYY')
                ELSE NULL
            END,
            CASE
                WHEN d.termination_date ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' THEN CAST(d.termination_date AS DATE)
                WHEN d.termination_date ~ '^[0-9]{{2}}\.[0-9]{{2}}\.[0-9]{{4}}$' THEN TO_DATE(d.termination_date, 'DD.MM.YYYY')
                ELSE NULL
            END
        FROM deduped d
        LEFT JOIN label l ON l.name = d.label_name
        ON CONFLICT (name) DO UPDATE SET
            label_id = EXCLUDED.label_id,
            effective_date = COALESCE(EXCLUDED.effective_date, right_holder.effective_date),
            termination_date = COALESCE(EXCLUDED.termination_date, right_holder.termination_date)
        RETURNING id;
        """), {"upload_id": upload_id}
    )
    count = result_rights.rowcount
    elapsed = time.time() - t0
    print(f"✅ Right holders вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"✅ Right holders вставлено: {count} ({elapsed:.1f} сек)")
    return count


def _sync_releases_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """4. ЗАПОЛНЯЕМ RELEASE (релизы/альбомы)"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result_releases = conn.execute(
        text(f"""
        WITH release_candidates AS (
            SELECT DISTINCT
                NULLIF(sc.upc, '') AS upc,
                COALESCE(NULLIF(sc.album_name, ''), 'Unknown Album') AS title,
                CASE 
                    WHEN NULLIF(sc.release_date, '') IS NOT NULL 
                    THEN CAST(sc.release_date AS DATE)
                    ELSE NULL 
                END AS release_date,
                l.id AS label_id,
                1 AS status,
                ROW_NUMBER() OVER (
                    PARTITION BY NULLIF(sc.upc, '') 
                    ORDER BY 
                        CASE WHEN l.id IS NOT NULL THEN 1 ELSE 2 END,
                        CASE WHEN NULLIF(sc.release_date, '') IS NOT NULL THEN 1 ELSE 2 END,
                        sc.id
                ) AS rn
            FROM {staging_table} sc
            LEFT JOIN label l ON l.name = sc.label_name
            WHERE COALESCE(NULLIF(sc.album_name, ''), 'Unknown Album') IS NOT NULL
              AND NULLIF(sc.upc, '') IS NOT NULL
              AND sc.upload_id = :upload_id
        )
        INSERT INTO release (upc, title, release_date, label_id, status)
        SELECT upc, title, release_date, label_id, status
        FROM release_candidates 
        WHERE rn = 1
        ON CONFLICT (upc) DO NOTHING
        RETURNING id;
        """), {"upload_id": upload_id}
    )
    count = result_releases.rowcount
    elapsed = time.time() - t0
    print(f"✅ Releases вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"✅ Releases вставлено: {count} ({elapsed:.1f} сек)")
    return count


def _sync_tracks_v2_isrc(conn, upload_id, staging_table="staging_catalog_v2"):
    """5. ЗАПОЛНЯЕМ TRACK (треки)"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result_tracks = conn.execute(
        text(f"""
        INSERT INTO track (isrc, label_own_code, title, title_norm_key, duration, explicit, resource_reference, meta)
        SELECT DISTINCT ON (sc.id)
            NULLIF(sc.isrc, '') AS isrc,
            NULLIF(sc.right_id, '') AS label_own_code,
            COALESCE(NULLIF(sc.track_name, ''), 'Unknown Track') AS title,
            sc.track_name_norm_key AS title_norm_key,
            sc.duration AS duration,
            sc.explicit::BOOLEAN AS explicit,
            NULLIF(sc.resource_reference, '') AS resource_reference,
            JSONB_BUILD_OBJECT(
                'track_number', NULLIF(sc.track_number, ''),
                'genre', NULLIF(sc.genre_name, ''),
                'has_ringtone', NULLIF(sc.has_ringtone, ''),
                'ringtone_upc', NULLIF(sc.ringtone_upc, ''),
                'ringtone_isrc', NULLIF(sc.ringtone_isrc, ''),
                'has_vclip', NULLIF(sc.has_vclip, ''),
                'vclip_isrc', NULLIF(sc.vclip_isrc, ''),
                'video_upc', NULLIF(sc.video_upc, ''),
                'has_lyrics', NULLIF(sc.has_lyrics, ''),
                'has_ttml', NULLIF(sc.has_ttml, ''),
                'sales_start_date', NULLIF(sc.sales_start_date, '')
            ) AS meta
        FROM {staging_table} sc
        WHERE  sc.isrc IS NOT NULL  AND sc.upload_id = :upload_id
            AND NOT EXISTS (
            SELECT 1 FROM track t2 
            WHERE sc.isrc IS NOT NULL  AND t2.isrc = sc.isrc  AND t2.label_own_code = NULLIF(sc.right_id, '')
        )
        ORDER BY sc.id;
    

        """), {"upload_id": upload_id}
    )
    count = result_tracks.rowcount
    elapsed = time.time() - t0
    print(f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
    return count

def _sync_tracks_v2_label_code(conn, upload_id, staging_table="staging_catalog_v2"):
    """5. ЗАПОЛНЯЕМ TRACK (треки)"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result_tracks = conn.execute(
        text(f"""
        INSERT INTO track (isrc, label_own_code, title, title_norm_key, duration, explicit, resource_reference, meta)
        SELECT DISTINCT ON (sc.id)
            NULLIF(sc.isrc, '') AS isrc,
            NULLIF(sc.right_id, '') AS label_own_code,
            COALESCE(NULLIF(sc.track_name, ''), 'Unknown Track') AS title,
            sc.track_name_norm_key AS title_norm_key,
            sc.duration AS duration,
            sc.explicit::BOOLEAN AS explicit,
            NULLIF(sc.resource_reference, '') AS resource_reference,
            JSONB_BUILD_OBJECT(
                'track_number', NULLIF(sc.track_number, ''),
                'genre', NULLIF(sc.genre_name, ''),
                'has_ringtone', NULLIF(sc.has_ringtone, ''),
                'ringtone_upc', NULLIF(sc.ringtone_upc, ''),
                'ringtone_isrc', NULLIF(sc.ringtone_isrc, ''),
                'has_vclip', NULLIF(sc.has_vclip, ''),
                'vclip_isrc', NULLIF(sc.vclip_isrc, ''),
                'video_upc', NULLIF(sc.video_upc, ''),
                'has_lyrics', NULLIF(sc.has_lyrics, ''),
                'has_ttml', NULLIF(sc.has_ttml, ''),
                'sales_start_date', NULLIF(sc.sales_start_date, '')
            ) AS meta
        FROM {staging_table} sc
        WHERE  sc.isrc IS NULL AND  sc.upload_id = :upload_id and NULLIF(sc.right_id, '') IS NOT NULL
            AND NOT EXISTS (
            SELECT 1 FROM track t2 
            WHERE (sc.isrc IS NULL ) 
                 AND t2.label_own_code = NULLIF(sc.right_id, '')
                 AND t2.title_norm_key = sc.track_name_norm_key
              
           )
        ORDER BY sc.id;

        """), {"upload_id": upload_id}
    )
    count = result_tracks.rowcount
    elapsed = time.time() - t0
    print(f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
    return count

    
def _sync_tracks_v2_name(conn, upload_id, staging_table="staging_catalog_v2"):
    """5. ЗАПОЛНЯЕМ TRACK (треки)"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result_tracks = conn.execute(
        text(f"""
        INSERT INTO track (isrc, label_own_code, title, title_norm_key, duration, explicit, resource_reference, meta)
        SELECT DISTINCT ON (sc.id)
            NULLIF(sc.isrc, '') AS isrc,
            NULLIF(sc.right_id, '') AS label_own_code,
            COALESCE(NULLIF(sc.track_name, ''), 'Unknown Track') AS title,
            sc.track_name_norm_key AS title_norm_key,
            sc.duration AS duration,
            sc.explicit::BOOLEAN AS explicit,
            NULLIF(sc.resource_reference, '') AS resource_reference,
            JSONB_BUILD_OBJECT(
                'track_number', NULLIF(sc.track_number, ''),
                'genre', NULLIF(sc.genre_name, ''),
                'has_ringtone', NULLIF(sc.has_ringtone, ''),
                'ringtone_upc', NULLIF(sc.ringtone_upc, ''),
                'ringtone_isrc', NULLIF(sc.ringtone_isrc, ''),
                'has_vclip', NULLIF(sc.has_vclip, ''),
                'vclip_isrc', NULLIF(sc.vclip_isrc, ''),
                'video_upc', NULLIF(sc.video_upc, ''),
                'has_lyrics', NULLIF(sc.has_lyrics, ''),
                'has_ttml', NULLIF(sc.has_ttml, ''),
                'sales_start_date', NULLIF(sc.sales_start_date, '')
            ) AS meta
        FROM {staging_table} sc
        WHERE  sc.isrc IS NULL AND sc.right_id IS NULL AND sc.upload_id = :upload_id
            AND NOT EXISTS (
                SELECT 1 FROM track t2 
                WHERE  ( t2.title_norm_key = sc.track_name_norm_key AND t2.label_own_code IS NULL )
            )
        ORDER BY sc.id;

        """), {"upload_id": upload_id}
    )
    count = result_tracks.rowcount
    elapsed = time.time() - t0
    print(f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
    return count


def _build_track_map_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """ЭТАП СОЗДАНИЯ ОДНОЗНАЧНОЙ КАРТЫ (MAP)"""
    t0 = time.time()
    conn.execute(
        text(f"""
        DROP TABLE IF EXISTS tmp_track_map;
        CREATE TEMP TABLE tmp_track_map AS
        SELECT 
            sc.id AS staging_id,
            t.id AS track_id,
            r.id AS release_id
        FROM {staging_table} sc
        JOIN track t ON t.isrc = sc.isrc  AND t.label_own_code = NULLIF(sc.right_id, '')
        LEFT JOIN release r ON r.upc = sc.upc
        WHERE sc.upload_id = :upload_id  AND sc.isrc IS NOT NULL
        
        UNION ALL

         SELECT 
            sc.id AS staging_id,
            t.id AS track_id,
            r.id AS release_id
        FROM {staging_table} sc
        JOIN track t ON t.title_norm_key = sc.track_name_norm_key   AND t.label_own_code = NULLIF(sc.right_id, '')
        LEFT JOIN release r ON r.upc = sc.upc
        WHERE sc.upload_id = :upload_id   AND (sc.isrc IS NULL ) AND NULLIF(sc.right_id, '') IS NOT NULL;
        
    
        CREATE INDEX idx_tmp_map_sid ON tmp_track_map(staging_id);
        CREATE INDEX idx_tmp_map_tid ON tmp_track_map(track_id);
        ANALYZE tmp_track_map;
        """), {"upload_id": upload_id}
    )
    elapsed = time.time() - t0
    print(f"✅ tmp_track_map создана ({elapsed:.1f} сек)")
    TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ tmp_track_map создана ({elapsed:.1f} сек)")


def _sync_track_releases_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """5.1 ЗАПОЛНЯЕМ TRACK_RELEASE (связь трек - релиз)"""
    t0 = time.time()
    result_track_release = conn.execute(
        text(f"""
            INSERT INTO track_release (track_id, release_id)
            SELECT DISTINCT ON (map.track_id)  map.track_id,  map.release_id
            FROM {staging_table} sc
            JOIN tmp_track_map map ON map.staging_id = sc.id
            WHERE map.release_id IS NOT NULL
            AND sc.upload_id = :upload_id
            -- ПРОВЕРКА 1: Не берем то, что уже физически есть в таблице связей
            AND NOT EXISTS (
                SELECT 1 FROM track_release tr
                WHERE tr.track_id = map.track_id
                    AND tr.release_id = map.release_id
            )
            ORDER BY map.track_id, map.release_id
            -- ПРОВЕРКА 2: Если вдруг между SELECT и INSERT проскочил дубль — игнорируем
            ON CONFLICT (track_id, release_id) DO NOTHING;
            """), {"upload_id": upload_id}
    )
    count = result_track_release.rowcount
    elapsed = time.time() - t0
    print(f"✅ Track_release вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Track_release вставлено: {count} ({elapsed:.1f} сек)")
    return count


def _sync_track_contributions_v2(conn, upload_id):
    """ЗАПОЛНЯЕМ TRACK_CONTRIBUTION напрямую из staging_person"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    
    # Теперь нам не нужен цикл по колонкам, так как все роли уже в staging_person
    result = conn.execute(text("""
        INSERT INTO track_contribution (track_id, person_id, role)
        SELECT DISTINCT
            map.track_id,
            p.id,
            sp.role
        FROM tmp_track_map map
        -- Связываем трек с его персонами из стейджинга по staging_id
        JOIN staging_person sp ON sp.staging_id = map.staging_id 
            AND sp.upload_id = :upload_id
        -- Находим финальный ID персоны в справочнике по нормализованному ключу
        JOIN person p ON p.norm_key_full = sp.full_name_norm_key
        ON CONFLICT (track_id, person_id, role) DO NOTHING;
    """), {"upload_id": upload_id})

    total_inserted = result.rowcount
    elapsed = time.time() - t0
    
    print(f"✅ ВСЕГО Track contributions вставлено: {total_inserted} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"✅ ВСЕГО Track contributions вставлено: {total_inserted} ({elapsed:.1f} сек)")
 
   
    return total_inserted


def _sync_track_rights_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """7. ЗАПОЛНЯЕМ TRACK_RIGHT (права на треки) — v2 структура с _INT/_MOB/_PUB"""
    # В v2: ar_label_treaty_number — один правообладатель для авторских прав
    #        rr_label_treaty_number — один правообладатель для смежных прав
    #        доли разбиты по типам использования: _INT, _MOB, _PUB
    t0 = time.time()
    mapping = [
        ("ar_label_treaty_number", "author_right_int", "Author", "INT"),
        ("ar_label_treaty_number", "author_right_mob", "Author", "MOB"),
        ("ar_label_treaty_number", "author_right_pub", "Author", "PUB"),
        ("rr_label_treaty_number", "related_right_id_int", "Related", "INT"),
        ("rr_label_treaty_number", "related_right_id_mob", "Related", "MOB"),
        ("rr_label_treaty_number", "related_right_id_pub", "Related", "PUB"),
    ]
    track_rights_count = 0
    for holder_col, share_col, cat_name, usage_code in mapping:
        sql = f"""
        INSERT INTO track_right (track_id, contract_id, right_holder_id, right_category_id, right_usage_type_id, share_percentage, region)
        SELECT DISTINCT ON (map.track_id, rh.id, rc.id, rut.id)
            map.track_id,
            NULL::BIGINT,
            rh.id,
            rc.id,
            rut.id,
            ROUND(CAST(NULLIF(REPLACE(sc.{share_col}, ',', '.'), '') AS NUMERIC), 2),
            sc.countries
        
        FROM {staging_table} sc
        JOIN tmp_track_map map ON map.staging_id = sc.id
        join track_label tl ON tl.track_id = map.track_id
        JOIN right_holder rh ON rh.name = sc.{holder_col}
        JOIN right_category rc ON rc.name = '{cat_name}'
        JOIN right_usage_type rut ON rut.code = '{usage_code}'
        WHERE sc.{holder_col} IS NOT NULL AND sc.{holder_col} != ''
        AND sc.upload_id = :upload_id
        AND NOT EXISTS (
            SELECT 1 FROM track_right tr
            join right_holder rh2 ON rh2.id = tr.right_holder_id
            WHERE tr.track_id = map.track_id
            AND tr.right_holder_id = rh.id
            AND tr.right_category_id = rc.id
            AND tr.right_usage_type_id = rut.id
            AND tl.label_id = rh.label_id
        )
        ORDER BY map.track_id, rh.id, rc.id, rut.id;
        """
        result = conn.execute(text(sql), {"upload_id": upload_id})
        count = result.rowcount
        track_rights_count += count
        print(f"✅ В {cat_name} ({usage_code}) вставлено: {count}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ В {cat_name} ({usage_code}) вставлено: {count}")

    elapsed = time.time() - t0
    print(f"🏁 ИТОГО вставлено в track_right: {track_rights_count} ({elapsed:.1f} сек)")
    TaskProgress.emit(getattr(current_task.request, 'id', None), f"🏁 ИТОГО вставлено в track_right: {track_rights_count} ({elapsed:.1f} сек)")
    return track_rights_count


def _sync_track_labels_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """8. ЗАПОЛНЯЕМ TRACK_LABEL (связь трек - лейбл)"""
    t0 = time.time()
    result_track_label = conn.execute(
        text(f"""
        INSERT INTO track_label (track_id, label_id)
        SELECT DISTINCT map.track_id, l.id
        FROM {staging_table} sc
        JOIN tmp_track_map map ON map.staging_id = sc.id
        JOIN label l ON l.name = sc.label_name
        WHERE sc.label_name IS NOT NULL AND sc.label_name != ''
        AND sc.upload_id = :upload_id
        ON CONFLICT (track_id, label_id) DO NOTHING;
        """), {"upload_id": upload_id}
    )
    count = result_track_label.rowcount
    elapsed = time.time() - t0
    print(f"✅ Связей track_label добавлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Связей track_label добавлено: {count} ({elapsed:.1f} сек)")
    return count


def _cleanup_staging_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """Очистка staging после синхронизации"""
    t0 = time.time()
    conn.execute(
        text(f"DELETE FROM {staging_table} WHERE upload_id = :uid"),
        {"uid": upload_id}
    )
    conn.execute(
        text("DELETE FROM staging_person WHERE upload_id = :uid"),
        {"uid": upload_id}
    )
    elapsed = time.time() - t0
    print(f"🧹 Стейджинг v2 очищен для сессии {upload_id} ({elapsed:.1f} сек)")
    TaskProgress.emit(getattr(current_task.request, 'id', None), f"🧹 Стейджинг v2 очищен для сессии {upload_id} ({elapsed:.1f} сек)")


# ===========================================================================
#  TASK 2: Синхронизация справочников из staging_catalog_v2
# ===========================================================================

@celery_app.task(name="sync_catalog_dictionaries", bind=True)
def sync_catalog_dictionaries(self, prev_result, version="v2"):
    upload_id = prev_result.get("upload_id") if isinstance(prev_result, dict) else prev_result
    task_id = getattr(self.request, 'id', None)
    success = False
    if version == "v2":
        staging_table = "staging_catalog_v2"
    else:    
        staging_table = "staging_catalog"
    try:
     
        # Phase 3: Основная синхронизация
        with engine.begin() as conn:
            print("📋 [v2] Начинаем синхронизацию справочников...")
            TaskProgress.emit(task_id, "📋 [v2] Начинаем синхронизацию справочников...")
            labels_count = _sync_labels_v2(conn, upload_id, staging_table=staging_table)
            persons_staging_count = _sync_persons_v2(conn, upload_id, staging_table=staging_table)

            # Phase 2: Нормализация (нужны закоммиченные данные)
            from .report_tasks import normalize_person_data, normalize_data
            print("📋 [v2] Нормализация staging_person...")
            TaskProgress.emit(task_id, "📋 [v2] Нормализация staging_person...")
            normalize_person_data("staging_person", "full_name", "tokens", "full_name_norm_key", connection=conn)
            print("📋 [v2] Нормализация staging_catalog_v2.track_name...")
            TaskProgress.emit(task_id, "📋 [v2] Нормализация staging_catalog_v2.track_name...")

            if version == "v2":
                normalize_data("staging_catalog_v2", "track_name", connection=conn)
            else:
                normalize_data("staging_catalog", "track_name", connection=conn)


            persons_count = _insert_unique_persons_v2(conn, upload_id)
            #rights_count = _sync_right_holders_v2(conn, upload_id)
        
            releases_count = _sync_releases_v2(conn, upload_id, staging_table=staging_table)
            
            tracks_count_isrc = _sync_tracks_v2_isrc(conn, upload_id, staging_table=staging_table)   
            tracks_count_code = _sync_tracks_v2_label_code(conn, upload_id, staging_table=staging_table)
           

            _build_track_map_v2(conn, upload_id, staging_table=staging_table)

            track_release_count = _sync_track_releases_v2(conn, upload_id, staging_table=staging_table)
            contributions_count = _sync_track_contributions_v2(conn, upload_id)

            #track_rights_count = _sync_track_rights_v2(conn, upload_id)
            _sync_track_labels_v2(conn, upload_id, staging_table=staging_table)

            if version == "v2":
                rights_count = _sync_right_holders_v2(conn, upload_id, staging_table=staging_table)
                track_rights_count = _sync_track_rights_v2(conn, upload_id, staging_table=staging_table)
            else:
                rights_count = _sync_right_holders_v1(conn, upload_id)
                track_rights_count = _sync_track_rights_v1(conn, upload_id)

            #_sync_track_labels_v2(conn, upload_id, staging_table=staging_table)

            conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_catalog_flat; "))
            conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_track_extended; "))
            print(f"🏁 Представления обновлены.")

            _cleanup_staging_v2(conn, upload_id, staging_table=staging_table)
            success = True

            return {
                "status": "success",
                "stats": {
                    "labels": labels_count,
                    "persons_staging": persons_staging_count,
                    "persons": persons_count,
                    "right_holders": rights_count,
                    "releases": releases_count,
                    "tracks": tracks_count_isrc + tracks_count_code,
                    "track_releases": track_release_count,
                    "track_contributions": contributions_count,
                    "track_rights": track_rights_count
                }
            }

    except Exception as e:
        print(f"[v2] ❌ Ошибка заполнения справочников: {e}")
        TaskProgress.emit(task_id, f"[v2] ❌ Ошибка заполнения справочников: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if not success:
            with engine.begin() as clean_conn:
                _cleanup_staging_v2(clean_conn, upload_id, staging_table=staging_table)
            TaskProgress.emit(task_id, "🧹 Staging очищен после ошибки")

def _sync_right_holders_v1(conn, upload_id):
    """3. ЗАПОЛНЯЕМ RIGHT_HOLDER для v1"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result_rights = conn.execute(
        text("""
        WITH right_holder_names AS (
            SELECT DISTINCT TRIM(ar_label_treaty_number_1) AS name FROM staging_catalog WHERE ar_label_treaty_number_1 IS NOT NULL AND TRIM(ar_label_treaty_number_1) != '' AND upload_id = :upload_id
            UNION
            SELECT DISTINCT TRIM(ar_label_treaty_number_2) AS name FROM staging_catalog WHERE ar_label_treaty_number_2 IS NOT NULL AND TRIM(ar_label_treaty_number_2) != '' AND upload_id = :upload_id
            UNION
            SELECT DISTINCT TRIM(ar_label_treaty_number_3) AS name FROM staging_catalog WHERE ar_label_treaty_number_3 IS NOT NULL AND TRIM(ar_label_treaty_number_3) != '' AND upload_id = :upload_id
            UNION
            SELECT DISTINCT TRIM(rr_label_treaty_number_1) AS name FROM staging_catalog WHERE rr_label_treaty_number_1 IS NOT NULL AND TRIM(rr_label_treaty_number_1) != '' AND upload_id = :upload_id
            UNION
            SELECT DISTINCT TRIM(rr_label_treaty_number_2) AS name FROM staging_catalog WHERE rr_label_treaty_number_2 IS NOT NULL AND TRIM(rr_label_treaty_number_2) != '' AND upload_id = :upload_id
            UNION
            SELECT DISTINCT TRIM(rr_label_treaty_number_3) AS name FROM staging_catalog WHERE rr_label_treaty_number_3 IS NOT NULL AND TRIM(rr_label_treaty_number_3) != '' AND upload_id = :upload_id
        )
        INSERT INTO right_holder (name, label_id)
        SELECT rhn.name, l.id FROM right_holder_names rhn
        JOIN label l ON l.name = (SELECT DISTINCT label_name FROM staging_catalog WHERE upload_id = :upload_id LIMIT 1)
        ON CONFLICT (name) DO NOTHING
        RETURNING id;
        """), {"upload_id": upload_id}
    )
    count = result_rights.rowcount
    elapsed = time.time() - t0
    print(f"✅ Right holders (v1) вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"✅ Right holders (v1) вставлено: {count} ({elapsed:.1f} сек)")
    return count

def _sync_track_rights_v1(conn, upload_id):
    """7. ЗАПОЛНЯЕМ TRACK_RIGHT для v1"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    mapping = [
        ("ar_label_treaty_number_1", "author_right_1", "Author"),
        ("ar_label_treaty_number_2", "author_right_2", "Author"),
        ("ar_label_treaty_number_3", "author_right_3", "Author"),
        ("rr_label_treaty_number_1", "related_right_id_1", "Related"),
        ("rr_label_treaty_number_2", "related_right_id_2", "Related"),
        ("rr_label_treaty_number_3", "related_right_id_3", "Related"),
    ]
    track_rights_count = 0
    for holder_col, share_col, cat_name in mapping:
        sql = f"""
        INSERT INTO track_right (track_id, contract_id, right_holder_id, right_category_id, right_usage_type_id, share_percentage, region_id)
        SELECT DISTINCT ON (map.track_id, rh.id, rc.id, rut.id)
            map.track_id,
            NULL::BIGINT,
            rh.id,
            rc.id,
            rut.id,
            COALESCE(NULLIF(REGEXP_REPLACE(TRIM(sc.{share_col}::text), '[^0-9.]', '', 'g'), '')::NUMERIC, 0.0),
            r.id
        FROM staging_catalog sc
        JOIN tmp_track_map map ON map.staging_id = sc.id
        JOIN right_holder rh ON rh.name = TRIM(sc.{holder_col})
        JOIN right_category rc ON rc.name = '{cat_name}'
        JOIN right_usage_type rut ON rut.code = sc.types_of_rights
        left join region r on r.code = sc.countries
        WHERE sc.{holder_col} IS NOT NULL AND TRIM(sc.{holder_col}) != ''
        AND sc.upload_id = :upload_id
        AND NOT EXISTS (
            SELECT 1 FROM track_right tr
            WHERE tr.track_id = map.track_id
            AND tr.right_holder_id = rh.id
            AND tr.right_category_id = rc.id
            AND tr.right_usage_type_id = rut.id
        )
        ORDER BY map.track_id, rh.id, rc.id, rut.id;
        """
        result = conn.execute(text(sql), {"upload_id": upload_id})
        count = result.rowcount
        track_rights_count += count
        print(f"✅ В {cat_name} ({holder_col}) вставлено: {count}")
        TaskProgress.emit(task_id, f"✅ В {cat_name} ({holder_col}) вставлено: {count}")
    elapsed = time.time() - t0
    print(f"🏁 ИТОГО вставлено в track_right (v1): {track_rights_count} ({elapsed:.1f} сек)")
    TaskProgress.emit(task_id, f"🏁 ИТОГО вставлено в track_right (v1): {track_rights_count} ({elapsed:.1f} сек)")
    return track_rights_count