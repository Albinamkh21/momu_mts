import os
import polars as pl
from sqlalchemy import create_engine, text
from core.celery_app import celery_app

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

@celery_app.task(name="process_catalog_file")
def process_catalog_file(file_path: str):
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File not found"}

    try:
        df = pl.read_excel(file_path) 
        
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
            "effective_date", "termination_date", "active_inactive", "resource_reference"
        ]

        for i in range(0, total_rows, chunk_size):
            chunk = df.slice(i, chunk_size)
            
            chunk.columns = db_columns
            
            chunk = clean_null_bytes(chunk)
            
            chunk.write_database(
                table_name="staging_catalog",
                connection=DATABASE_URL,
                if_table_exists="append",
               engine="adbc"
            )
            print(f"📦 Загружен батч: {i} - {i + len(chunk)}")

        os.remove(file_path)
        return {"status": "success", "total_rows": total_rows}

    except Exception as e:
        print(f"❌ Ошибка воркера: {str(e)}")
        return {"status": "error", "message": str(e)}


@celery_app.task(name="sync_catalog_dictionaries")
def sync_catalog_dictionaries():
    try:
        with engine.begin() as conn:
            print("📋 Начинаем синхронизацию справочников...")
            
            # --- 1. ЗАПОЛНЯЕМ LABEL ---
            result_labels = conn.execute(text("""
                INSERT INTO label (name) 
                SELECT DISTINCT TRIM(s.label_name)
                FROM staging_catalog s
                WHERE s.label_name IS NOT NULL 
                AND TRIM(s.label_name) != ''
                AND NOT EXISTS (
                     SELECT 1 FROM label l 
                     WHERE l.name = TRIM(s.label_name)
                 )
                RETURNING id;
            """))
            labels_count = result_labels.rowcount
            print(f"✅ Labels вставлено: {labels_count}")

            # --- 2. ЗАПОЛНЯЕМ PERSON (из 4-х колонок) ---
            result_persons = conn.execute(text("""
              WITH person_names AS (
                SELECT DISTINCT TRIM(unnest(clean_and_split(artist_name))) AS name
                FROM staging_catalog WHERE artist_name IS NOT NULL AND artist_name != ''
                
                UNION
                
                SELECT DISTINCT TRIM(unnest(clean_and_split(track_artist_name))) AS name
                FROM staging_catalog WHERE track_artist_name IS NOT NULL AND track_artist_name != ''
                
                UNION
                
                SELECT DISTINCT TRIM(unnest(clean_and_split(composer))) AS name
                FROM staging_catalog WHERE composer IS NOT NULL AND composer != ''
                
                UNION
                
                SELECT DISTINCT TRIM(unnest(clean_and_split(lyricist))) AS name
                FROM staging_catalog WHERE lyricist IS NOT NULL AND lyricist != ''
                
                UNION
                
                SELECT DISTINCT TRIM(unnest(clean_and_split(authors))) AS name
                FROM staging_catalog WHERE authors IS NOT NULL AND authors != ''
            )
            INSERT INTO person (full_name)
            SELECT DISTINCT name 
            FROM person_names 
            WHERE name IS NOT NULL AND name != ''
             ON CONFLICT (full_name) DO NOTHING
                """))
            persons_count = result_persons.rowcount
            print(f"✅ Persons вставлено: {persons_count}")

            # --- 3. ЗАПОЛНЯЕМ RIGHT_HOLDER ---
            result_rights = conn.execute(text("""
                WITH right_holder_names AS (
                    SELECT DISTINCT TRIM(ar_label_treaty_number_1) AS name
                    FROM staging_catalog 
                    WHERE ar_label_treaty_number_1 IS NOT NULL AND TRIM(ar_label_treaty_number_1) != ''
                    
                    UNION
                    
                    SELECT DISTINCT TRIM(ar_label_treaty_number_2) AS name
                    FROM staging_catalog 
                    WHERE ar_label_treaty_number_2 IS NOT NULL AND TRIM(ar_label_treaty_number_2) != ''
                    
                    UNION
                    
                    SELECT DISTINCT TRIM(ar_label_treaty_number_3) AS name
                    FROM staging_catalog 
                    WHERE ar_label_treaty_number_3 IS NOT NULL AND TRIM(ar_label_treaty_number_3) != ''
                    
                    UNION
                    
                    SELECT DISTINCT TRIM(rr_label_treaty_number_1) AS name
                    FROM staging_catalog 
                    WHERE rr_label_treaty_number_1 IS NOT NULL AND TRIM(rr_label_treaty_number_1) != ''
                    
                    UNION
                    
                    SELECT DISTINCT TRIM(rr_label_treaty_number_2) AS name
                    FROM staging_catalog 
                    WHERE rr_label_treaty_number_2 IS NOT NULL AND TRIM(rr_label_treaty_number_2) != ''
                    
                    UNION
                    
                    SELECT DISTINCT TRIM(rr_label_treaty_number_3) AS name
                    FROM staging_catalog 
                    WHERE rr_label_treaty_number_3 IS NOT NULL AND TRIM(rr_label_treaty_number_3) != ''
                )
                INSERT INTO right_holder (name)
                SELECT name 
                FROM right_holder_names
                ON CONFLICT (name) DO NOTHING
                RETURNING id;
            """))
            rights_count = result_rights.rowcount
            print(f"✅ Right holders вставлено: {rights_count}")

            # --- 4. ЗАПОЛНЯЕМ RELEASE (релизы/альбомы) ---
            result_releases = conn.execute(text("""
                INSERT INTO release (upc, title, release_date, label_id, status)
                SELECT DISTINCT 
                    NULLIF(TRIM(sc.upc), '') AS upc,
                    COALESCE(NULLIF(TRIM(sc.album_name), ''), 'Unknown Album') AS title,
                    CASE 
                        WHEN NULLIF(TRIM(sc.release_date), '') IS NOT NULL 
                        THEN CAST(TRIM(sc.release_date) AS DATE)
                        ELSE NULL 
                    END AS release_date,
                    l.id AS label_id,
                    CASE 
                        WHEN LOWER(TRIM(sc.active_inactive)) = 'active' THEN 'Active'
                        WHEN LOWER(TRIM(sc.active_inactive)) = 'inactive' THEN 'Inactive' 
                        ELSE 'Active'
                    END AS status
                FROM staging_catalog sc
                LEFT JOIN label l ON l.name = TRIM(sc.label_name)
                WHERE COALESCE(NULLIF(TRIM(sc.album_name), ''), 'Unknown Album') IS NOT NULL
                GROUP BY 
                    NULLIF(TRIM(sc.upc), ''),
                    COALESCE(NULLIF(TRIM(sc.album_name), ''), 'Unknown Album'),
                    CASE 
                        WHEN NULLIF(TRIM(sc.release_date), '') IS NOT NULL 
                        THEN CAST(TRIM(sc.release_date) AS DATE)
                        ELSE NULL 
                    END,
                    l.id,
                    CASE 
                        WHEN LOWER(TRIM(sc.active_inactive)) = 'active' THEN 'Active'
                        WHEN LOWER(TRIM(sc.active_inactive)) = 'inactive' THEN 'Inactive' 
                        ELSE 'Active'
                    END
                ON CONFLICT (upc) DO UPDATE SET
                    title = EXCLUDED.title,
                    release_date = EXCLUDED.release_date,
                    label_id = EXCLUDED.label_id,
                    status = EXCLUDED.status
                WHERE EXCLUDED.upc IS NOT NULL
                RETURNING id;
            """))
            releases_count = result_releases.rowcount
            print(f"✅ Releases вставлено: {releases_count}")

            # --- 5. ЗАПОЛНЯЕМ TRACK (треки) ---
            result_tracks = conn.execute(text("""
                INSERT INTO track (release_id, isrc, label_own_code, title, duration, explicit, resource_reference, meta)
                SELECT DISTINCT ON (sc.id)
                    r.id AS release_id,
                    NULLIF(TRIM(sc.isrc), '') AS isrc,
                    NULLIF(TRIM(sc.right_id), '') AS label_own_code,
                    COALESCE(NULLIF(TRIM(sc.track_name), ''), 'Unknown Track') AS title,
                    CASE 
                        WHEN sc.duration ~ '^[0-9]+:[0-9]+:[0-9]+$' THEN 
                            CAST(sc.duration AS INTERVAL)
                        WHEN sc.duration ~ '^[0-9]+:[0-9]+$' THEN 
                            CAST('00:' || sc.duration AS INTERVAL)
                        ELSE NULL 
                    END AS duration,
                    CASE 
                        WHEN LOWER(TRIM(sc.explicit)) IN ('true', 'yes', '1', 'explicit') THEN TRUE
                        ELSE FALSE 
                    END AS explicit,
                    NULLIF(TRIM(sc.resource_reference), '') AS resource_reference,
                    JSONB_BUILD_OBJECT(
                        'track_number', NULLIF(TRIM(sc.track_number), ''),
                        'genre', NULLIF(TRIM(sc.genre_name), ''),
                        'has_ringtone', NULLIF(TRIM(sc.has_ringtone), ''),
                        'ringtone_upc', NULLIF(TRIM(sc.ringtone_upc), ''),
                        'ringtone_isrc', NULLIF(TRIM(sc.ringtone_isrc), ''),
                        'has_vclip', NULLIF(TRIM(sc.has_vclip), ''),
                        'vclip_isrc', NULLIF(TRIM(sc.vclip_isrc), ''),
                        'video_upc', NULLIF(TRIM(sc.video_upc), ''),
                        'has_lyrics', NULLIF(TRIM(sc.has_lyrics), ''),
                        'has_ttml', NULLIF(TRIM(sc.has_ttml), ''),
                        'countries', NULLIF(TRIM(sc.countries), ''),
                        'types_of_rights', NULLIF(TRIM(sc.types_of_rights), ''),
                        'sales_start_date', NULLIF(TRIM(sc.sales_start_date), '')
                    ) AS meta
                FROM staging_catalog sc
                LEFT JOIN release r ON (
                CASE 
                    WHEN NULLIF(TRIM(sc.upc), '') IS NOT NULL THEN r.upc = TRIM(sc.upc)
                    ELSE r.title = NULLIF(TRIM(sc.album_name), '')
                END
            )
            ORDER BY sc.id, r.id;
            """))
            tracks_count = result_tracks.rowcount
            print(f"✅ Tracks вставлено: {tracks_count}")

            result_contributions = conn.execute(text("""
                INSERT INTO track_contribution (track_id, person_id, role)
                SELECT DISTINCT ON (t.id, p.id, unpivoted.role)
                    t.id AS track_id, 
                    p.id AS person_id, 
                    unpivoted.role
                FROM staging_catalog sc
                -- Разворачиваем 5 колонок в строки за ОДИН проход
                CROSS JOIN LATERAL (
                    VALUES 
                        (sc.artist_name, 'artist_name'),
                        (sc.track_artist_name, 'track_artist_name'),
                        (sc.composer, 'composer'),
                        (sc.lyricist, 'lyricist'),
                        (sc.authors, 'authors')
                ) AS unpivoted(val, role)

                JOIN track t ON (
                    CASE 
                        WHEN sc.isrc IS NOT NULL AND sc.isrc != '' THEN t.isrc = sc.isrc
                        ELSE t.title = sc.track_name
                    END
                )
                CROSS JOIN LATERAL unnest(string_to_array(unpivoted.val, ',')) AS raw_name
                JOIN person p ON p.full_name = TRIM(raw_name)
                WHERE unpivoted.val IS NOT NULL AND unpivoted.val != ''
                ORDER BY t.id, p.id, unpivoted.role;
            """))




            contributions_count = result_contributions.rowcount
            print(f"✅ Track contributions вставлено: {contributions_count}")

            # --- 7. ЗАПОЛНЯЕМ TRACK_RIGHT (права на треки) ---
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
                INSERT INTO track_right (track_id, contract_id, right_holder_id, right_category_id, share_percentage)
                SELECT DISTINCT ON (t.id, rh.id, rc.id)
                    t.id,
                    NULL::BIGINT,
                    rh.id,
                    rc.id,
                    COALESCE(NULLIF(REGEXP_REPLACE(TRIM(sc.{share_col}::text), '[^0-9.]', '', 'g'), '')::NUMERIC, 0.0)
                FROM staging_catalog sc
                JOIN track t ON (
                    (NULLIF(TRIM(sc.isrc), '') IS NOT NULL AND t.isrc = UPPER(REGEXP_REPLACE(sc.isrc, '[^A-Za-z0-9]', '', 'g')))
                    OR 
                    (NULLIF(TRIM(sc.isrc), '') IS NULL AND t.title = TRIM(sc.track_name))
                )
                JOIN right_holder rh ON rh.name = TRIM(sc.{holder_col})
                JOIN right_category rc ON rc.name = '{cat_name}'
                WHERE sc.{holder_col} IS NOT NULL AND TRIM(sc.{holder_col}) != ''
                ORDER BY t.id, rh.id, rc.id;
                """
                result = conn.execute(text(sql))
                count = result.rowcount
                track_rights_count += count
                print(f"✅ В {cat_name} ({holder_col}) вставлено: {count}")

            print(f"🏁 ИТОГО вставлено в track_right: {track_rights_count}")

            return {
                "status": "success",
                "stats": {
                    "labels": labels_count,
                    "persons": persons_count,
                    "right_holders": rights_count,
                    "releases": releases_count,
                    "tracks": tracks_count,
                    "track_contributions": contributions_count,
                    "track_rights": track_rights_count
                }
            }

    except Exception as e:
        print(f"❌ Ошибка заполнения справочников: {e}")
        return {"status": "error", "message": str(e)}


def check_catalog_integrity():
    """Проверяет целостность заливки каталога: ищет потери между staging и справочниками."""
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
            SELECT DISTINCT TRIM(label_name) AS name FROM staging_catalog
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
                (SELECT COUNT(*) FROM person_names WHERE name IS NOT NULL AND name != '') AS staging_count,
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
            FROM staging_catalog sc
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



@celery_app.task(name="export_normalized_catalog_to_flat")
def export_normalized_catalog_to_flat(output_path: str = None):
    query = """
        WITH contributors_agg AS (
            SELECT 
                tc.track_id,
                string_agg(p.full_name, ', ') FILTER (WHERE tc.role = 'artist_name') AS artist_name,
                string_agg(p.full_name, ', ') FILTER (WHERE tc.role = 'track_artist_name') AS track_artist_name,
                string_agg(p.full_name, ', ') FILTER (WHERE tc.role = 'composer') AS composer,
                string_agg(p.full_name, ', ') FILTER (WHERE tc.role = 'lyricist') AS lyricist,
                string_agg(p.full_name, ', ') FILTER (WHERE tc.role = 'authors') AS authors
            FROM track_contribution tc
            JOIN person p ON p.id = tc.person_id
            GROUP BY tc.track_id
        ),
        rights_ranked AS (
            SELECT 
                tr.track_id,
                rh.name AS holder_name,
                tr.share_percentage AS share,
                rc.name AS category,
                row_number() OVER (PARTITION BY tr.track_id, rc.name ORDER BY tr.id) AS rank
            FROM track_right tr
            JOIN right_holder rh ON rh.id = tr.right_holder_id
            JOIN right_category rc ON rc.id = tr.right_category_id
        )
        SELECT 
            r.upc::TEXT, 
            t.isrc::TEXT, 
            t.title::TEXT AS track_name,
            (t.meta->>'genre')::TEXT AS genre_name,
            r.title::TEXT AS album_name,
            NULL::TEXT AS album_single,
            (t.meta->>'track_number')::TEXT AS track_number,
            c.artist_name::TEXT,
            c.track_artist_name::TEXT,
            c.composer::TEXT,
            c.lyricist::TEXT,
            c.authors::TEXT,
            
            CASE WHEN t.explicit THEN 'Да' ELSE 'Нет' END AS explicit,
            
            to_char(t.duration, 'MI:SS') AS duration,
            
            l.name::TEXT AS label_name,
            
            (SELECT SUM(share) FROM rights_ranked WHERE track_id = t.id AND category = 'Author')::NUMERIC AS total_author_right,
            NULL::TEXT AS right_id,
            MAX(CASE WHEN rr.category = 'Author' AND rr.rank = 1 THEN rr.share END)::NUMERIC AS author_right_1,
            MAX(CASE WHEN rr.category = 'Author' AND rr.rank = 1 THEN rr.holder_name END)::TEXT AS ar_label_treaty_number_1,
            MAX(CASE WHEN rr.category = 'Author' AND rr.rank = 2 THEN rr.share END)::NUMERIC AS author_right_2,
            MAX(CASE WHEN rr.category = 'Author' AND rr.rank = 2 THEN rr.holder_name END)::TEXT AS ar_label_treaty_number_2,
            MAX(CASE WHEN rr.category = 'Author' AND rr.rank = 3 THEN rr.share END)::NUMERIC AS author_right_3,
            MAX(CASE WHEN rr.category = 'Author' AND rr.rank = 3 THEN rr.holder_name END)::TEXT AS ar_label_treaty_number_3,
            
            (SELECT SUM(share) FROM rights_ranked WHERE track_id = t.id AND category = 'Related')::NUMERIC AS total_related_right,
            MAX(CASE WHEN rr.category = 'Related' AND rr.rank = 1 THEN rr.share END)::NUMERIC AS related_right_id_1,
            MAX(CASE WHEN rr.category = 'Related' AND rr.rank = 1 THEN rr.holder_name END)::TEXT AS rr_label_treaty_number_1,
            MAX(CASE WHEN rr.category = 'Related' AND rr.rank = 2 THEN rr.share END)::NUMERIC AS related_right_id_2,
            MAX(CASE WHEN rr.category = 'Related' AND rr.rank = 2 THEN rr.holder_name END)::TEXT AS rr_label_treaty_number_2,
            MAX(CASE WHEN rr.category = 'Related' AND rr.rank = 3 THEN rr.share END)::NUMERIC AS related_right_id_3,
            MAX(CASE WHEN rr.category = 'Related' AND rr.rank = 3 THEN rr.holder_name END)::TEXT AS rr_label_treaty_number_3,
            
            (t.meta->>'types_of_rights')::TEXT AS types_of_rights,
            (t.meta->>'countries')::TEXT AS countries,
            NULL::TEXT AS create_date,
            (r.release_date)::TEXT,
            (t.meta->>'sales_start_date')::TEXT AS sales_start_date,
            
            CASE WHEN (t.meta->>'has_ringtone')::boolean THEN 'Да' ELSE 'Нет' END AS has_ringtone,
            (t.meta->>'ringtone_upc')::TEXT AS ringtone_upc,
            (t.meta->>'ringtone_isrc')::TEXT AS ringtone_isrc,
            CASE WHEN (t.meta->>'has_vclip')::boolean THEN 'Да' ELSE 'Нет' END AS has_vclip,
            (t.meta->>'vclip_isrc')::TEXT AS vclip_isrc,
            (t.meta->>'video_upc')::TEXT AS video_upc,
            CASE WHEN (t.meta->>'has_lyrics')::boolean THEN 'Да' ELSE 'Нет' END AS has_lyrics,
            CASE WHEN (t.meta->>'has_ttml')::boolean THEN 'Да' ELSE 'Нет' END AS has_ttml,
            
            NULL::TEXT AS effective_date,
            NULL::TEXT AS termination_date,
            r.status::TEXT AS active_inactive,
            t.resource_reference::TEXT
        FROM track t
        JOIN release r ON r.id = t.release_id
        LEFT JOIN label l ON l.id = r.label_id
        LEFT JOIN contributors_agg c ON c.track_id = t.id
        LEFT JOIN rights_ranked rr ON rr.track_id = t.id
        GROUP BY 
            t.id, r.id, l.id, c.track_id, 
            c.artist_name, c.track_artist_name, c.composer, c.lyricist, c.authors
        ORDER BY r.upc, (t.meta->>'track_number')::int;
    """
    
    try:
        with engine.connect() as conn:
            df = pl.read_database(
                query=query, 
                connection=conn,
                infer_schema_length=None 
            )

        if output_path:
            if output_path.endswith('.xlsx'):
                df.write_excel(output_path)
            else:
                df.write_csv(output_path)
            return {"status": "success", "rows_exported": len(df), "path": output_path}
        
        return {"status": "success", "total_rows": len(df), "sample": df.head(5).to_dicts()}

    except Exception as e:
        print(f"❌ Ошибка экспорта каталога: {e}")
        return {"status": "error", "message": str(e)}




def clean_null_bytes(df: pl.DataFrame) -> pl.DataFrame:
    """
    1. Принудительно кастит всё в String
    2. Вычищает null-байты из всего датафрейма
    """
    try:
        df = df.with_columns([pl.col("*").cast(pl.String)])
        
        return df.with_columns([
            pl.col("*").str.replace_all(r"\x00", "", literal=True)
        ])
    except Exception as e:
        print(f"⚠️ Ошибка при жесткой очистке: {e}")
        return df