import os
import uuid
from datetime import datetime
import time
import polars as pl
from polars import lit
from sqlalchemy import create_engine, text
from core.celery_app import celery_app
from .utils import clean_null_bytes
import uuid
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)


# ===========================================================================
#  TASK 1: Загрузка файла в staging_catalog_v2
# ===========================================================================

@celery_app.task(name="process_catalog_file_v2", bind=True)
def process_catalog_file_v2(self, file_path: str, user_id: str, original_filename: str = ""):
    print(f"📂 Task process_catalog_file_v2[{self.request.id}] файл: {original_filename}")
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File not found"}

    upload_id = str(uuid.uuid4())
    start_time = datetime.now()    

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
                table_name="staging_catalog_v2",
                connection=DATABASE_URL,
                if_table_exists="append",
                engine="adbc"
            )
            print(f"[v2] 📦 Загружен батч: {i} - {i + len(chunk)}")

        os.remove(file_path)
        return {"status": "success", "total_rows": total_rows, "upload_id": upload_id}

    except Exception as e:
        print(f"[v2] ❌ Ошибка воркера: {str(e)}")
        return {"status": "error", "message": str(e)}


# ===========================================================================
#  Вспомогательные функции для каждого этапа синхронизации
# ===========================================================================

def _sync_labels_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """1. ЗАПОЛНЯЕМ LABEL"""
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
    return count


def _sync_persons_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """2. ЗАПОЛНЯЕМ PERSON (из 5-ти колонок)"""
    t0 = time.time()
    result_persons = conn.execute(
        text(f"""
        WITH person_names AS (
            SELECT DISTINCT TRIM(unnest(clean_and_split(artist_name))) AS name
            FROM {staging_table} WHERE artist_name IS NOT NULL AND artist_name != '' AND upload_id = :upload_id

            UNION

            SELECT DISTINCT TRIM(unnest(clean_and_split(track_artist_name))) AS name
            FROM {staging_table} WHERE track_artist_name IS NOT NULL AND track_artist_name != '' AND upload_id = :upload_id

            UNION

            SELECT DISTINCT TRIM(unnest(clean_and_split(composer))) AS name
            FROM {staging_table} WHERE composer IS NOT NULL AND composer != '' AND upload_id = :upload_id

            UNION

            SELECT DISTINCT TRIM(unnest(clean_and_split(lyricist))) AS name
            FROM {staging_table} WHERE lyricist IS NOT NULL AND lyricist != '' AND upload_id = :upload_id

            UNION

            SELECT DISTINCT TRIM(unnest(clean_and_split(authors))) AS name
            FROM {staging_table} WHERE authors IS NOT NULL AND authors != '' AND upload_id = :upload_id
        )
        INSERT INTO person (full_name)
        SELECT DISTINCT name 
        FROM person_names 
        WHERE name IS NOT NULL AND name != ''
         ON CONFLICT (full_name) DO NOTHING
        """), {"upload_id": upload_id}
    )
    count = result_persons.rowcount
    elapsed = time.time() - t0
    print(f"✅ Persons вставлено: {count} ({elapsed:.1f} сек)")
    return count


def _sync_right_holders_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """3. ЗАПОЛНЯЕМ RIGHT_HOLDER"""
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
    return count


def _sync_releases_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """4. ЗАПОЛНЯЕМ RELEASE (релизы/альбомы)"""
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
    return count


def _sync_tracks_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """5. ЗАПОЛНЯЕМ TRACK (треки)"""
    t0 = time.time()
    result_tracks = conn.execute(
        text(f"""
        INSERT INTO track (isrc, label_own_code, title, duration, explicit, resource_reference, meta)
        SELECT DISTINCT ON (sc.id)
            NULLIF(sc.isrc, '') AS isrc,
            NULLIF(sc.right_id, '') AS label_own_code,
            COALESCE(NULLIF(sc.track_name, ''), 'Unknown Track') AS title,
            CAST(sc.duration AS INTERVAL) AS duration,
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
                'countries', NULLIF(sc.countries, ''),
                'types_of_rights', NULLIF(sc.types_of_rights, ''),
                'sales_start_date', NULLIF(sc.sales_start_date, '')
            ) AS meta
        FROM {staging_table} sc
        WHERE  
        sc.upload_id = :upload_id
        AND NOT EXISTS (
            SELECT 1 FROM track t2 
            WHERE
            (
                sc.isrc IS NOT NULL AND sc.isrc != '' 
                AND t2.isrc = sc.isrc  AND t2.label_own_code = NULLIF(sc.right_id, '')
            )
            OR 
            (
                (sc.isrc IS NULL OR sc.isrc = '') 
                AND t2.label_own_code = NULLIF(sc.right_id, '')
                AND t2.title = COALESCE(NULLIF(sc.track_name, ''), 'Unknown Track')
            )
            OR
            (sc.isrc IS NULL AND sc.right_id IS NULL AND t2.title = sc.track_name AND t2.label_own_code IS NULL AND t2.isrc IS NULL)
        )
        ORDER BY sc.id;
        """), {"upload_id": upload_id}
    )
    count = result_tracks.rowcount
    elapsed = time.time() - t0
    print(f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
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
            t2.id AS track_id,
            r.id AS release_id
        FROM {staging_table} sc
        JOIN track t2 ON (
            (
                (sc.isrc IS NOT NULL AND sc.isrc != '') 
                AND t2.isrc = sc.isrc  AND t2.label_own_code = NULLIF(sc.right_id, '')
            )
            OR 
            (
                (sc.isrc IS NULL OR sc.isrc = '') 
                AND t2.label_own_code = NULLIF(sc.right_id, '')
                AND t2.title = COALESCE(NULLIF(sc.track_name, ''), 'Unknown Track')
            )
            OR
            (sc.isrc IS NULL AND sc.right_id IS NULL AND t2.title = sc.track_name AND t2.label_own_code IS NULL AND t2.isrc IS NULL)
        )
        LEFT JOIN release r ON r.upc = sc.upc
        WHERE sc.upload_id = :upload_id;
        CREATE INDEX idx_tmp_map_sid ON tmp_track_map(staging_id);
        CREATE INDEX idx_tmp_map_tid ON tmp_track_map(track_id);
        ANALYZE tmp_track_map;
        """), {"upload_id": upload_id}
    )
    elapsed = time.time() - t0
    print(f"✅ tmp_track_map создана ({elapsed:.1f} сек)")


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
    return count


def _sync_track_contributions_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """6. ЗАПОЛНЯЕМ TRACK_CONTRIBUTION (связь трек - участник)"""
    t0 = time.time()
    total_inserted = 0
    
    roles_to_sync = [
        ('artist_name', 'artist_name'),
        ('track_artist_name', 'track_artist_name'),
        ('composer', 'composer'),
        ('lyricist', 'lyricist'),
        ('authors', 'authors')
    ]

    for col_name, role_label in roles_to_sync:
        t_role = time.time()
        
        # Выполняем вставку для конкретной роли
        result = conn.execute(text(f"""
            WITH staging_names AS (
                SELECT
                    id AS staging_id,
                    TRIM(unnest(clean_and_split({col_name}))) AS clean_name
                FROM {staging_table}
                WHERE {col_name} IS NOT NULL AND {col_name} != ''
                AND upload_id = :upload_id
            ),
            matched_contributions AS (
                SELECT
                    sn.staging_id,
                    p.id AS person_id
                FROM staging_names sn
                JOIN person p ON p.full_name = sn.clean_name
            )
            INSERT INTO track_contribution (track_id, person_id, role)
            SELECT DISTINCT
                map.track_id,
                mc.person_id,
                :role
            FROM tmp_track_map map
            JOIN matched_contributions mc ON mc.staging_id = map.staging_id
            ON CONFLICT (track_id, person_id, role) DO NOTHING;
        """), {"upload_id": upload_id, "role": role_label})
        
        # Считаем сколько добавлено именно этой ролью
        role_count = result.rowcount
        total_inserted += role_count
        
        role_elapsed = time.time() - t_role
        print(f"  └─ Роль '{role_label}': вставлено {role_count} ({role_elapsed:.2f} сек)")

    elapsed_total = time.time() - t0
    print(f"✅ ВСЕГО Track contributions вставлено: {total_inserted} ({elapsed_total:.1f} сек)")
    
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
        INSERT INTO track_right (track_id, contract_id, right_holder_id, right_category_id, right_usage_type_id, share_percentage)
        SELECT DISTINCT ON (map.track_id, rh.id, rc.id, rut.id)
            map.track_id,
            NULL::BIGINT,
            rh.id,
            rc.id,
            rut.id,
            ROUND(CAST(NULLIF(REPLACE(sc.{share_col}, ',', '.'), '') AS NUMERIC), 2)
        
        FROM {staging_table} sc
        JOIN tmp_track_map map ON map.staging_id = sc.id
        JOIN right_holder rh ON rh.name = sc.{holder_col}
        JOIN right_category rc ON rc.name = '{cat_name}'
        JOIN right_usage_type rut ON rut.code = '{usage_code}'
        WHERE sc.{holder_col} IS NOT NULL AND sc.{holder_col} != ''
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
        print(f"✅ В {cat_name} ({usage_code}) вставлено: {count}")

    elapsed = time.time() - t0
    print(f"🏁 ИТОГО вставлено в track_right: {track_rights_count} ({elapsed:.1f} сек)")
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
    return count


def _cleanup_staging_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """Очистка staging после синхронизации"""
    t0 = time.time()
    conn.execute(
        text(f"DELETE FROM {staging_table} WHERE upload_id = :uid"),
        {"uid": upload_id}
    )
    elapsed = time.time() - t0
    print(f"🧹 Стейджинг v2 очищен для сессии {upload_id} ({elapsed:.1f} сек)")


# ===========================================================================
#  TASK 2: Синхронизация справочников из staging_catalog_v2
# ===========================================================================

@celery_app.task(name="sync_catalog_dictionaries_v2")
def sync_catalog_dictionaries_v2(prev_result):
    upload_id = prev_result.get("upload_id") if isinstance(prev_result, dict) else prev_result
    try:
        with engine.begin() as conn:
            print("📋 [v2] Начинаем синхронизацию справочников...")

            labels_count = _sync_labels_v2(conn, upload_id)
            persons_count = _sync_persons_v2(conn, upload_id)
            rights_count = _sync_right_holders_v2(conn, upload_id)
            releases_count = _sync_releases_v2(conn, upload_id)
            tracks_count = _sync_tracks_v2(conn, upload_id)

            _build_track_map_v2(conn, upload_id)

            track_release_count = _sync_track_releases_v2(conn, upload_id)
            contributions_count = _sync_track_contributions_v2(conn, upload_id)
            track_rights_count = _sync_track_rights_v2(conn, upload_id)
            _sync_track_labels_v2(conn, upload_id)

            _cleanup_staging_v2(conn, upload_id)


          

            return {
                "status": "success",
                "stats": {
                    "labels": labels_count,
                    "persons": persons_count,
                    "right_holders": rights_count,
                    "releases": releases_count,
                    "tracks": tracks_count,
                    "track_releases": track_release_count,
                    "track_contributions": contributions_count,
                    "track_rights": track_rights_count
                }
            }

    except Exception as e:
        print(f"[v2] ❌ Ошибка заполнения справочников: {e}")
        return {"status": "error", "message": str(e)}


