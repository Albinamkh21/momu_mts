"""
Двусторонний Diff между стейджингом (staging_catalog_v2) и боевым каталогом
(track / track_contribution / track_right) для одного лейбла.

Всё сравнение выполняется средствами PostgreSQL через TEMP TABLE + JSONB,
Python здесь только последовательно выполняет SQL и возвращает результат.
"""

import time
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import List, Dict, Any
from services.broadcaster import TaskProgress

# Колонки в формате staging_catalog_v2, которые мы сопоставляем со "старыми"
# (действующими в track/track_label/track_right/track_contribution) значениями.
# upc/album_name/album_single в нормализованных таблицах не хранятся -> для old всегда None.
CATALOG_ROW_FIELDS = [
    "track_id", "right_id", "upc", "isrc", "track_name", "genre_name",
    "album_name", "album_single", "track_number", "artist_name",
    "track_artist_name", "composer", "lyricist", "authors",
    "explicit", "duration", "label_name",
    "author_right_int", "author_right_mob", "author_right_pub", "ar_label_treaty_number",
    "related_right_id_int", "related_right_id_mob", "related_right_id_pub", "rr_label_treaty_number",
]

# field_name из staging_track_diff -> какие колонки итоговой строки он затрагивает
DIFF_FIELD_TO_COLUMNS = {
    "artist_name": ["artist_name"],
    "track_artist_name": ["track_artist_name"],
    "composer": ["composer"],
    "lyricist": ["lyricist"],
    "authors": ["authors"],
    "track_rights": [
        "author_right_int", "author_right_mob", "author_right_pub", "ar_label_treaty_number",
        "related_right_id_int", "related_right_id_mob", "related_right_id_pub", "rr_label_treaty_number",
    ],
}


def _clean_value(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_to_dict(row) -> Dict[str, Any]:
    return {k: _clean_value(v) for k, v in dict(row).items()}


def update_staging_track_ids(conn, upload_id: str, task_id: str):
    TaskProgress.emit(task_id,"Starting track update in staging_catalog_v2")
    print("Starting track update in staging_catalog_v2")
    query = text("""
            
            UPDATE staging_catalog_v2 sc
            SET track_id = t.id
            FROM track t
            WHERE sc.upload_id = :upload_id
            AND sc.track_id IS NULL
            AND sc.isrc IS NOT NULL
            AND t.isrc = sc.isrc
            AND t.label_own_code = NULLIF(sc.right_id, '');

           
            UPDATE staging_catalog_v2 sc
            SET track_id = t.id
            FROM track t
            WHERE sc.upload_id = :upload_id
            AND sc.track_id IS NULL
            AND sc.isrc IS NULL
            AND t.label_own_code = NULLIF(sc.right_id, '')
            AND t.title_norm_key = sc.track_name_norm_key;
    """)
    conn.execute(query, {"upload_id": upload_id})
    TaskProgress.emit(task_id,"Finished track update in staging_catalog_v2")
    print("Finished track update in staging_catalog_v2")


def save_track_contribution_diff(conn, upload_id: str, task_id: str):
    t0 = time.time()
    
    # 1. Создаем таблицу для хранения диффов, если она еще не существует
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS staging_track_diff (
            id SERIAL PRIMARY KEY,
            track_id BIGINT,
            track_name TEXT,
            upload_id VARCHAR(255),
            field_name VARCHAR(255),
            old_value TEXT,
            new_value TEXT
        );
    """))
    
    # Очищаем предыдущие результаты для текущего upload_id (полезно при перезапусках таски)
    conn.execute(text("""
        DELETE FROM staging_track_diff WHERE upload_id = :upload_id;
    """), {"upload_id": upload_id})
    
    # Список ролей для проверки
    roles = [
        'artist_name',
        'authors',
        'composer',
        'lyricist',
        'track_artist_name'
    ]
    
    total_diffs = 0
    
    # 2. Выполняем запрос для каждой роли
    for role in roles:
        sql = """
        WITH target_track AS (
            SELECT 
                sc.id AS staging_id,
                sc.track_id,
                sc.track_name
            FROM staging_catalog_v2 sc
            WHERE sc.track_id IS NOT NULL 
              AND sc.upload_id = :upload_id
        ),
        old_data AS (
            SELECT 
                tt.staging_id,
                p.full_name,
                unnest(p.tokens) AS token 
            FROM target_track tt
            JOIN track_contribution tc ON tc.track_id::bigint = tt.track_id::bigint
            JOIN person p ON p.id = tc.person_id
            WHERE LOWER(TRIM(tc.role)) = :role
        ),
        old_roles AS (
            SELECT 
                staging_id,
                STRING_AGG(DISTINCT full_name, ', ') AS old_authors_text,
                ARRAY_AGG(token ORDER BY token) AS old_tokens_arr
            FROM old_data
            GROUP BY staging_id
        ),
        new_data AS (
            SELECT 
                sp.staging_id,
                sp.full_name,
                unnest(sp.tokens) AS token
            FROM staging_person sp
            JOIN target_track tt ON tt.staging_id::bigint = sp.staging_id::bigint
            WHERE sp.upload_id = :upload_id 
              AND LOWER(TRIM(sp.role)) = :role
        ),
        new_roles AS (
            SELECT 
                staging_id,
                STRING_AGG(DISTINCT full_name, ', ') AS new_authors_text,
                ARRAY_AGG(token ORDER BY token) AS new_tokens_arr
            FROM new_data
            GROUP BY staging_id
        )
        INSERT INTO staging_track_diff (
            track_id, 
            track_name, 
            upload_id, 
            field_name, 
            old_value, 
            new_value
        )
        SELECT 
            tt.track_id::bigint,
            tt.track_name,
            :upload_id AS upload_id,
            :role AS field_name,
            o.old_authors_text AS old_value,
            n.new_authors_text AS new_value
        FROM target_track tt
        LEFT JOIN old_roles o ON o.staging_id::bigint = tt.staging_id::bigint
        LEFT JOIN new_roles n ON n.staging_id::bigint = tt.staging_id::bigint
        WHERE o.old_tokens_arr IS DISTINCT FROM n.new_tokens_arr
          AND (o.old_tokens_arr IS NOT NULL OR n.new_tokens_arr IS NOT NULL);
        """
        
        result = conn.execute(text(sql), {
            "upload_id": upload_id, 
            "role": role
        })
        total_diffs += result.rowcount

    elapsed = time.time() - t0
    msg = f"✅ Найдено и сохранено отличий по авторам: {total_diffs} ({elapsed:.1f} сек)"
    print(msg)
    
    # Если в проекте используется класс TaskProgress для Celery, раскомментируйте:
    # TaskProgress.emit(task_id, msg)
    
    return total_diffs

    


def save_track_right_diff(conn, upload_id: str, task_id: str):
    TaskProgress.emit(task_id, "Starting track update in staging_catalog_v2")
    print("Starting track update in staging_catalog_v2")
    
    # Очистка предыдущих расхождений по этому upload_id (опционально, для идемпотентности)
    conn.execute(text("""
        DELETE FROM staging_track_diff 
        WHERE upload_id = :upload_id AND field_name = 'track_rights';
    """), {"upload_id": upload_id})

    sql = """
    WITH target_track AS (
        SELECT 
            sc.id AS staging_id,
            sc.track_id,
            sc.track_name,
            sc.ar_label_treaty_number,
            sc.rr_label_treaty_number,
            sc.author_right_int,
            sc.author_right_mob,
            sc.author_right_pub,
            sc.related_right_id_int,
            sc.related_right_id_mob,
            sc.related_right_id_pub
        FROM staging_catalog_v2 sc
        WHERE sc.track_id IS NOT NULL 
          AND sc.upload_id = :upload_id
    ),

    -- 1. Разворачиваем 6 колонок без текстовых обработок
    raw_new_rights AS (
        SELECT 
            tt.staging_id,
            v.cat_code,
            v.usage_code,
            v.holder_name,
            v.share_str::numeric(5,2) AS share_percentage
        FROM target_track tt
        CROSS JOIN LATERAL (
            VALUES 
                ('Author',  'INT', tt.ar_label_treaty_number, tt.author_right_int),
                ('Author',  'MOB', tt.ar_label_treaty_number, tt.author_right_mob),
                ('Author',  'PUB', tt.ar_label_treaty_number, tt.author_right_pub),
                ('Related', 'INT', tt.rr_label_treaty_number, tt.related_right_id_int),
                ('Related', 'MOB', tt.rr_label_treaty_number, tt.related_right_id_mob),
                ('Related', 'PUB', tt.rr_label_treaty_number, tt.related_right_id_pub)
        ) AS v(cat_code, usage_code, holder_name, share_str)
        WHERE (v.holder_name IS NOT NULL AND v.holder_name != '')
           OR (v.share_str IS NOT NULL AND v.share_str != '')
    ),

    -- 2. Прямые JOIN со справочниками (без LOWER/UPPER)
    new_data AS (
        SELECT 
            rnr.staging_id,
            rc.id AS right_category_id,
            rut.id AS right_usage_type_id,
            rh.id AS right_holder_id,
            rnr.share_percentage,
            rc.name || '/' || rut.code || ': ' || COALESCE(rh.name, rnr.holder_name, '') || ' [id=' || COALESCE(rh.id::text, 'НЕ_НАЙДЕН') || '] (' || COALESCE(rnr.share_percentage::text, '0') || '%)' AS right_str,
            rc.id::text || ':' || rut.id::text || ':' || COALESCE(rh.id::text, rnr.holder_name) || ':' || COALESCE(rnr.share_percentage, 0)::text AS right_key
        FROM raw_new_rights rnr
        JOIN right_category rc ON rc.name = rnr.cat_code
        JOIN right_usage_type rut ON rut.code = rnr.usage_code
        LEFT JOIN right_holder rh ON rh.name = rnr.holder_name
    ),
    new_rights AS (
        SELECT 
            staging_id,
            STRING_AGG(right_str, '; ' ORDER BY right_category_id, right_usage_type_id, COALESCE(right_holder_id, 0)) AS new_rights_text,
            ARRAY_AGG(right_key ORDER BY right_category_id, right_usage_type_id, COALESCE(right_holder_id, 0)) AS new_rights_arr
        FROM new_data
        GROUP BY staging_id
    ),

    -- 3. Данные из БД без преобразующих функций
    old_data AS (
        SELECT 
            tt.staging_id,
            tr.right_category_id,
            tr.right_usage_type_id,
            tr.right_holder_id,
            tr.share_percentage,
            rc.name || '/' || rut.code || ': ' || COALESCE(rh.name, tr.right_holder_id::text) || ' [id=' || tr.right_holder_id || '] (' || COALESCE(tr.share_percentage::text, '0') || '%)' AS right_str,
            tr.right_category_id::text || ':' || tr.right_usage_type_id::text || ':' || COALESCE(tr.right_holder_id::text, '') || ':' || COALESCE(tr.share_percentage, 0)::text AS right_key
        FROM target_track tt
        JOIN track_right tr ON tr.track_id = tt.track_id::bigint
        JOIN right_category rc ON rc.id = tr.right_category_id
        JOIN right_usage_type rut ON rut.id = tr.right_usage_type_id
        LEFT JOIN right_holder rh ON rh.id = tr.right_holder_id
    ),
    old_rights AS (
        SELECT 
            staging_id,
            STRING_AGG(right_str, '; ' ORDER BY right_category_id, right_usage_type_id, COALESCE(right_holder_id, 0)) AS old_rights_text,
            ARRAY_AGG(right_key ORDER BY right_category_id, right_usage_type_id, COALESCE(right_holder_id, 0)) AS old_rights_arr
        FROM old_data
        GROUP BY staging_id
    )

    -- 4. Сохранение результатов в таблицу staging_track_diff
    INSERT INTO staging_track_diff (
        track_id, 
        track_name, 
        upload_id, 
        field_name, 
        old_value, 
        new_value
    )
    SELECT 
        tt.track_id::bigint,
        tt.track_name,
        :upload_id AS upload_id,
        'track_rights' AS field_name,
        o.old_rights_text AS old_value,
        n.new_rights_text AS new_value
    FROM target_track tt
    LEFT JOIN old_rights o ON o.staging_id = tt.staging_id
    LEFT JOIN new_rights n ON n.staging_id = tt.staging_id
    WHERE o.old_rights_arr IS DISTINCT FROM n.new_rights_arr
      AND (o.old_rights_arr IS NOT NULL OR n.new_rights_arr IS NOT NULL);
    """
    
    # Выполнение запроса
    result = conn.execute(text(sql), {"upload_id": upload_id})
    
    TaskProgress.emit(task_id, "Finished track update in staging_catalog_v2")
    print("Finished track update in staging_catalog_v2")
    
    return result.rowcount







def generate_catalog_diff(conn: Connection, upload_id: str, label_id: int) -> List[Dict[str, Any]]:
    """
    Собирает данные по трекам, у которых save_track_contribution_diff/save_track_right_diff
    уже нашли отличия (таблица staging_track_diff), в формате staging_catalog_v2 —
    для показа пользователю на проверку перед применением изменений.

    Возвращает ПЛОСКИЙ список строк (готовый для вывода в таблицу на UI): для каждого
    изменившегося трека — сначала строка row_type="old" (текущие данные из track /
    track_label / track_right / track_contribution), сразу за ней row_type="new"
    (данные из staging_catalog_v2, т.е. то, что пришло в файле). Обе строки несут
    одинаковый changed_fields — список ключей, которые отличаются, чтобы фронт мог
    подсветить именно изменившиеся ячейки.

    upc/album_name/album_single для "old" всегда None — эти поля не хранятся
    в нормализованных таблицах track/track_label/track_right/track_contribution.
    """

    # 1. Треки, по которым найдены отличия в этой загрузке
    diff_rows = conn.execute(
        text("""
            SELECT track_id, field_name, old_value, new_value
            FROM staging_track_diff
            WHERE upload_id = :upload_id
            ORDER BY track_id
        """),
        {"upload_id": upload_id},
    ).mappings().all()

    if not diff_rows:
        return []

    track_ids = sorted({row["track_id"] for row in diff_rows})

    # 2. "Новые" строки — напрямую из staging_catalog_v2
    new_rows = conn.execute(
        text("""
            SELECT DISTINCT ON (sc.track_id::bigint)
                sc.track_id::bigint AS track_id,
                sc.right_id,
                sc.upc,
                sc.isrc,
                sc.track_name,
                sc.genre_name,
                sc.album_name,
                sc.album_single,
                sc.track_number,
                sc.artist_name,
                sc.track_artist_name,
                sc.composer,
                sc.lyricist,
                sc.authors,
                sc.explicit,
                sc.duration,
                sc.label_name,
                sc.author_right_int,
                sc.author_right_mob,
                sc.author_right_pub,
                sc.ar_label_treaty_number,
                sc.related_right_id_int,
                sc.related_right_id_mob,
                sc.related_right_id_pub,
                sc.rr_label_treaty_number
            FROM staging_catalog_v2 sc
            WHERE sc.upload_id = :upload_id
              AND sc.track_id IS NOT NULL
              AND sc.track_id::bigint = ANY(:track_ids)
            ORDER BY sc.track_id::bigint, sc.id DESC
        """),
        {"upload_id": upload_id, "track_ids": track_ids},
    ).mappings().all()
    new_by_track = {row["track_id"]: _row_to_dict(row) for row in new_rows}

    # 3. "Старые" строки — собираем из track / track_label / track_right / track_contribution
    old_rows = conn.execute(
        text("""
            WITH old_contrib AS (
                SELECT
                    tc.track_id,
                    STRING_AGG(DISTINCT p.full_name, ', ') FILTER (WHERE tc.role = 'artist_name') AS artist_name,
                    STRING_AGG(DISTINCT p.full_name, ', ') FILTER (WHERE tc.role = 'track_artist_name') AS track_artist_name,
                    STRING_AGG(DISTINCT p.full_name, ', ') FILTER (WHERE tc.role = 'composer') AS composer,
                    STRING_AGG(DISTINCT p.full_name, ', ') FILTER (WHERE tc.role = 'lyricist') AS lyricist,
                    STRING_AGG(DISTINCT p.full_name, ', ') FILTER (WHERE tc.role = 'authors') AS authors
                FROM track_contribution tc
                JOIN person p ON p.id = tc.person_id
                WHERE tc.track_id = ANY(:track_ids)
                GROUP BY tc.track_id
            ),
            old_rights AS (
                SELECT
                    tr.track_id,
                    MAX(rh.name) FILTER (WHERE rc.name = 'Author') AS ar_label_treaty_number,
                    MAX(tr.share_percentage) FILTER (WHERE rc.name = 'Author' AND rut.code = 'INT') AS author_right_int,
                    MAX(tr.share_percentage) FILTER (WHERE rc.name = 'Author' AND rut.code = 'MOB') AS author_right_mob,
                    MAX(tr.share_percentage) FILTER (WHERE rc.name = 'Author' AND rut.code = 'PUB') AS author_right_pub,
                    MAX(rh.name) FILTER (WHERE rc.name = 'Related') AS rr_label_treaty_number,
                    MAX(tr.share_percentage) FILTER (WHERE rc.name = 'Related' AND rut.code = 'INT') AS related_right_id_int,
                    MAX(tr.share_percentage) FILTER (WHERE rc.name = 'Related' AND rut.code = 'MOB') AS related_right_id_mob,
                    MAX(tr.share_percentage) FILTER (WHERE rc.name = 'Related' AND rut.code = 'PUB') AS related_right_id_pub
                FROM track_right tr
                JOIN right_category rc ON rc.id = tr.right_category_id
                JOIN right_usage_type rut ON rut.id = tr.right_usage_type_id
                LEFT JOIN right_holder rh ON rh.id = tr.right_holder_id
                WHERE tr.track_id = ANY(:track_ids)
                GROUP BY tr.track_id
            ),
            old_label AS (
                SELECT DISTINCT ON (tl.track_id)
                    tl.track_id,
                    l.name AS label_name
                FROM track_label tl
                JOIN label l ON l.id = tl.label_id
                WHERE tl.track_id = ANY(:track_ids)
                  AND (:label_id IS NULL OR tl.label_id = :label_id)
                ORDER BY tl.track_id, tl.id
            )
            SELECT
                t.id AS track_id,
                t.label_own_code AS right_id,
                NULL::text AS upc,
                t.isrc,
                t.title AS track_name,
                t.meta ->> 'genre' AS genre_name,
                NULL::text AS album_name,
                NULL::text AS album_single,
                t.meta ->> 'track_number' AS track_number,
                oc.artist_name,
                oc.track_artist_name,
                oc.composer,
                oc.lyricist,
                oc.authors,
                t.explicit,
                t.duration,
                ol.label_name,
                orr.author_right_int,
                orr.author_right_mob,
                orr.author_right_pub,
                orr.ar_label_treaty_number,
                orr.related_right_id_int,
                orr.related_right_id_mob,
                orr.related_right_id_pub,
                orr.rr_label_treaty_number
            FROM track t
            LEFT JOIN old_contrib oc ON oc.track_id = t.id
            LEFT JOIN old_rights orr ON orr.track_id = t.id
            LEFT JOIN old_label ol ON ol.track_id = t.id
            WHERE t.id = ANY(:track_ids)
        """),
        {"track_ids": track_ids, "label_id": label_id},
    ).mappings().all()
    old_by_track = {row["track_id"]: _row_to_dict(row) for row in old_rows}

    # 4. Группируем сырые диффы по треку и переводим field_name -> задетые колонки
    diffs_by_track: Dict[int, List[Dict[str, Any]]] = {}
    for row in diff_rows:
        diffs_by_track.setdefault(row["track_id"], []).append({
            "field_name": row["field_name"],
            "old_value": row["old_value"],
            "new_value": row["new_value"],
        })

    # 5. Плоский список строк old/new подряд для каждого трека — готов для таблицы на UI
    rows: List[Dict[str, Any]] = []
    for track_id in track_ids:
        track_diffs = diffs_by_track.get(track_id, [])
        changed_fields = sorted({
            col
            for d in track_diffs
            for col in DIFF_FIELD_TO_COLUMNS.get(d["field_name"], [d["field_name"]])
        })

        for row_type, values_by_track in (("old", old_by_track), ("new", new_by_track)):
            row = {field: None for field in CATALOG_ROW_FIELDS}
            row.update(values_by_track.get(track_id, {}))
            row["track_id"] = track_id
            row["row_type"] = row_type
            row["changed_fields"] = changed_fields
            rows.append(row)

    return rows