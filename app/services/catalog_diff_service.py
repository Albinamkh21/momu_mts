from datetime import datetime
import time
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection
from typing import List, Dict, Any, Optional
from services.broadcaster import TaskProgress

from celery import current_task
from services.broadcaster import TaskProgress

import uuid
import sys

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
    TaskProgress.emit(upload_id,"Starting track update in staging_catalog_v2")
    print("Starting track update in staging_catalog_v2")
    query = text("""
            
            UPDATE staging_catalog_v2 sc
            SET track_id = t.id, status = 'existing'
            FROM track t
            WHERE sc.upload_id = :upload_id
            AND sc.track_id IS NULL
            AND sc.isrc IS NOT NULL
            AND t.isrc = sc.isrc
            AND t.label_own_code = NULLIF(sc.right_id, '');

           
            UPDATE staging_catalog_v2 sc
            SET track_id = t.id, status = 'existing'
            FROM track t
            WHERE sc.upload_id = :upload_id
            AND sc.track_id IS NULL
            AND sc.isrc IS NULL
            AND t.label_own_code = NULLIF(sc.right_id, '')
            AND t.title_norm_key = sc.track_name_norm_key;
    """)
    conn.execute(query, {"upload_id": upload_id})
    TaskProgress.emit(upload_id,"Finished track update in staging_catalog_v2")
    print("Finished track update in staging_catalog_v2")



def update_catalog_statistics(conn, upload_id: str, task_id: str) -> dict:
    TaskProgress.emit(upload_id, "Starting track update statistics in staging_catalog_v2")
    print("Starting track update statistics in staging_catalog_v2")
    
    query = text("""
        WITH modified_tracks AS (
            -- Получаем уникальные ID треков, у которых есть хотя бы одно изменение
            SELECT DISTINCT track_id
            FROM staging_track_diff
            WHERE upload_id = :upload_id 
              AND track_id IS NOT NULL
        )
        SELECT
            COUNT(1) FILTER (WHERE sc.status = 'new') AS new_count,
            COUNT(1) FILTER (WHERE sc.status = 'existing') AS existing_count,
            COUNT(1) FILTER (WHERE sc.status = 'existing' AND mt.track_id IS NOT NULL) AS modified_count
        FROM staging_catalog_v2 sc
        LEFT JOIN modified_tracks mt ON mt.track_id = sc.track_id
        WHERE sc.upload_id = :upload_id
    """)
    
    row = conn.execute(query, {"upload_id": upload_id}).fetchone()
    
    new_count = row[0] or 0
    existing_count = row[1] or 0
    modified_count = row[2] or 0
    
    msg = (
        f"Finished statistics calculation: "
        f"Новых треков: {new_count}, "
        f"Существующих: {existing_count} (из них измененных: {modified_count})"
    )
    
    TaskProgress.emit(upload_id, msg)
    print(msg)
    
    return {
        "new_tracks": new_count,
        "existing_tracks": existing_count,
        "modified_tracks": modified_count
    }




def find_track_contribution_diff(conn, upload_id: str, task_id: str):
    t0 = time.time()
    msg = f"Starting track contribution diff for upload_id: {upload_id}"
    print(msg)
    # 1. Создаем таблицу для хранения диффов, если она еще не существует

    # 1. Форсируем создание индивидуального плана для каждого upload_id (PostgreSQL 12+)
    conn.execute(text("SET plan_cache_mode = 'force_custom_plan';"))
    # 2. Отключаем JIT-компиляцию для этого запроса, чтобы сэкономить ~4 секунды
    conn.execute(text("SET jit = off;"))

    # Опционально: если staging-таблицы заливаются прямо в этой же Celery-задаче 
    # за секунды до этого запроса, автовакуум не успевает собрать по ним статистику.
    # Это сильно поможет планировщику:
    conn.execute(text("ANALYZE staging_catalog_v2;"))
    conn.execute(text("ANALYZE staging_person;"))


    # Очищаем предыдущие результаты для текущего upload_id
    conn.execute(text("""
        DELETE FROM staging_track_diff
        WHERE upload_id = :upload_id;
    """), {"upload_id": upload_id})

    # Список ролей
    roles = [
        'artist_name',
        'authors',
        'composer',
        'lyricist',
        'track_artist_name'
    ]

    # Формируем VALUES для ролей
    role_values = ", ".join(
        f"(:role_{i}, {i})"
        for i in range(len(roles))
    )

    role_params = {
        f"role_{i}": role
        for i, role in enumerate(roles)
    }
    role_params["upload_id"] = upload_id

    sql = f"""
        WITH target_track AS (
            SELECT
                sc.id AS staging_id,
                sc.track_id,
                sc.track_name
            FROM staging_catalog_v2 sc
            WHERE sc.track_id IS NOT NULL
              AND sc.upload_id = :upload_id
        ),

        roles(role, role_order) AS (
            VALUES {role_values}
        ),

        old_data AS (
            SELECT
                tt.staging_id,
                tc.role,
                p.full_name,
                unnest(p.tokens) AS token
            FROM target_track tt
            JOIN track_contribution tc
                ON tc.track_id = tt.track_id
            JOIN person p
                ON p.id = tc.person_id
            JOIN roles r
                ON r.role = tc.role
        ),

        old_roles AS (
            SELECT
                staging_id,
                role,
                STRING_AGG(DISTINCT full_name, ', ') AS old_authors_text,
                ARRAY_AGG(token ORDER BY token) AS old_tokens_arr
            FROM old_data
            GROUP BY staging_id, role
        ),

        new_data AS (
            SELECT
                sp.staging_id,
                sp.role,
                sp.full_name,
                unnest(sp.tokens) AS token
            FROM staging_person sp
            JOIN target_track tt
                ON tt.staging_id = sp.staging_id
            JOIN roles r
                ON r.role = sp.role
            WHERE sp.upload_id = :upload_id
        ),

        new_roles AS (
            SELECT
                staging_id,
                role,
                STRING_AGG(DISTINCT full_name, ', ') AS new_authors_text,
                ARRAY_AGG(token ORDER BY token) AS new_tokens_arr
            FROM new_data
            GROUP BY staging_id, role
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
            tt.track_id,
            tt.track_name,
            :upload_id AS upload_id,
            r.role AS field_name,
            o.old_authors_text AS old_value,
            n.new_authors_text AS new_value
        FROM target_track tt
        CROSS JOIN roles r
        LEFT JOIN old_roles o
            ON o.staging_id = tt.staging_id
           AND o.role = r.role
        LEFT JOIN new_roles n
            ON n.staging_id = tt.staging_id
           AND n.role = r.role
        WHERE o.old_tokens_arr IS DISTINCT FROM n.new_tokens_arr
          AND (
              o.old_tokens_arr IS NOT NULL
              OR n.new_tokens_arr IS NOT NULL
          )
        ORDER BY r.role_order; """

    result = conn.execute(text(sql), role_params)

   
    total_diffs = result.rowcount

    elapsed = time.time() - t0
    msg = f"✅ Найдено и сохранено отличий по авторам: {total_diffs} ({elapsed:.1f} сек)"
    print(msg)

    # TaskProgress.emit(upload_id, msg)
    conn.execute(text("SET plan_cache_mode = 'auto';"))
    conn.execute(text("SET jit = on;"))

    return total_diffs


def find_track_right_diff(conn, upload_id: str, task_id: str):
    TaskProgress.emit(upload_id, f" Starting track right diff for upload_id: {upload_id}")
    print(f"  Starting track right diff for upload_id: {upload_id}")
    
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
        JOIN track_right tr ON tr.track_id = tt.track_id 
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
        tt.track_id,
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
    
    TaskProgress.emit(upload_id, "Finished track update in staging_catalog_v2")
    print("Finished track update in staging_catalog_v2")
    
    return result.rowcount


def find_tracks_common_info_diff(conn, upload_id: str, task_id: str):
    """
    Сравнивает базовую информацию о треках между staging_catalog_v2 и track таблицей.
    Проверяет различия в:
    - isrc (строка)
    - duration (интервал)
    - explicit (boolean)
    - resource_reference (текст)
    - label_own_code (строка из right_id)
    - meta полем (JSONB): genre_name, track_number, has_ringtone, ringtone_upc, ringtone_isrc, 
      has_vclip, vclip_isrc, video_upc, has_lyrics, has_ttml, sales_start_date
    """
    TaskProgress.emit(upload_id, "Starting common track info comparison")
    print("Starting common track info comparison")
    
    # Очистка предыдущих расхождений по этому upload_id для common_info
    conn.execute(text("""
        DELETE FROM staging_track_diff 
        WHERE upload_id = :upload_id AND field_name IN 
            ('isrc', 'duration', 'explicit', 'resource_reference', 'label_own_code', 
             'track_number', 'genre', 'has_ringtone', 'ringtone_upc', 'ringtone_isrc',
             'has_vclip', 'vclip_isrc', 'video_upc', 'has_lyrics', 'has_ttml', 'sales_start_date');
    """), {"upload_id": upload_id})
    
    t0 = time.time()
    total_diffs = 0
    
    # Список полей для сравнения (простые поля)
    common_fields = [
        ('isrc', 'sc.isrc', 't.isrc'),
        ('duration', 'sc.duration', "t.duration::text"),  # Преобразуем INTERVAL в text для сравнения
        ('explicit', 'sc.explicit', 't.explicit::text'),
        ('resource_reference', 'sc.resource_reference', 't.resource_reference'),
        ('label_own_code', 'NULLIF(sc.right_id, \'\')', 't.label_own_code'),
    ]
    
    # Сравнение простых полей
    for field_name, staging_col, track_col in common_fields:
        sql = f"""
        WITH target_track AS (
            SELECT 
                sc.id AS staging_id,
                sc.track_id,
                sc.track_name,
                {staging_col} AS staging_value,
                {track_col} AS track_value
            FROM staging_catalog_v2 sc
            LEFT JOIN track t ON sc.track_id::bigint = t.id
            WHERE sc.track_id IS NOT NULL 
              AND sc.upload_id = :upload_id
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
            tt.track_id,
            tt.track_name,
            :upload_id AS upload_id,
            :field_name AS field_name,
            COALESCE(tt.track_value::text, '') AS old_value,
            COALESCE(tt.staging_value::text, '') AS new_value
        FROM target_track tt
        WHERE COALESCE(tt.staging_value::text, '') IS DISTINCT FROM COALESCE(tt.track_value::text, '')
          AND (tt.staging_value IS NOT NULL OR tt.track_value IS NOT NULL);
        """
        
        result = conn.execute(text(sql), {
            "upload_id": upload_id,
            "field_name": field_name
        })
        total_diffs += result.rowcount
    
    # Сравнение полей из meta (JSONB) и соответствующих staging_catalog_v2 колонок
    # Маппинг: staging_column -> meta_key (как оно хранится в track.meta)
    meta_fields = [
        ('track_number', 'track_number', "'track_number'"),
        ('genre_name', 'genre', "'genre'"),
        ('has_ringtone', 'has_ringtone', "'has_ringtone'"),
        ('ringtone_upc', 'ringtone_upc', "'ringtone_upc'"),
        ('ringtone_isrc', 'ringtone_isrc', "'ringtone_isrc'"),
        ('has_vclip', 'has_vclip', "'has_vclip'"),
        ('vclip_isrc', 'vclip_isrc', "'vclip_isrc'"),
        ('video_upc', 'video_upc', "'video_upc'"),
        ('has_lyrics', 'has_lyrics', "'has_lyrics'"),
        ('has_ttml', 'has_ttml', "'has_ttml'"),
        ('sales_start_date', 'sales_start_date', "'sales_start_date'"),
    ]
    
    for staging_col, meta_field_name, meta_key in meta_fields:
        sql = f"""
        WITH target_track AS (
            SELECT 
                sc.id AS staging_id,
                sc.track_id,
                sc.track_name,
                NULLIF(sc.{staging_col}, '') AS staging_value,
                t.meta ->> {meta_key} AS track_value
            FROM staging_catalog_v2 sc
            LEFT JOIN track t ON sc.track_id = t.id
            WHERE sc.track_id IS NOT NULL 
              AND sc.upload_id = :upload_id
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
            tt.track_id,
            tt.track_name,
            :upload_id AS upload_id,
            :field_name AS field_name,
            COALESCE(tt.track_value, '') AS old_value,
            COALESCE(tt.staging_value::text, '') AS new_value
        FROM target_track tt
        WHERE COALESCE(tt.staging_value::text, '') IS DISTINCT FROM COALESCE(tt.track_value, '')
          AND (tt.staging_value IS NOT NULL OR tt.track_value IS NOT NULL);
        """
        
        result = conn.execute(text(sql), {
            "upload_id": upload_id,
            "field_name": meta_field_name
        })
        total_diffs += result.rowcount
    
    elapsed = time.time() - t0
    msg = f"✅ Найдено и сохранено отличий в базовой информации трека: {total_diffs} ({elapsed:.1f} сек)"
    print(msg)
    TaskProgress.emit(upload_id, msg)
    
    return total_diffs


def get_catalog_diff(conn: Connection, upload_id: Optional[str], label_id: int) -> List[Dict[str, Any]]:
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
    print(f"Getting catalog diff for upload_id={upload_id}, label_id={label_id}")
    if not upload_id:
        row = conn.execute(
            text("""
                SELECT upload_id 
                FROM catalog_upload 
                WHERE label_id = :label_id AND status = 'PROCESSING' 
                ORDER BY created_at DESC 
                LIMIT 1
            """),
            {"label_id": label_id}
        ).fetchone()
        
        if not row:
            return []  # Нет загрузок в статусе PROCESSING для этого лейбла
            
        upload_id = row[0]

    rows: List[Dict[str, Any]] = []

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
            SELECT DISTINCT ON (sc.track_id)
                sc.track_id AS track_id,
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
              AND sc.track_id = ANY(:track_ids)
            ORDER BY sc.track_id, sc.id DESC
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
    TaskProgress.emit(upload_id, f"✅ Labels вставлено: {count} ({elapsed:.1f} сек)")
    return count


def _sync_persons_v2(conn, upload_id, staging_table="staging_catalog_v2"):
    """2. ЗАПОЛНЯЕМ STAGING_PERSON (из 5-ти колонок)"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()

    conn.execute(
        text("DELETE FROM staging_person WHERE upload_id = :upload_id"),
        {"upload_id": upload_id}
    )
    
    result_persons = conn.execute(
        text(f"""
        WITH person_names AS (
            SELECT id AS staging_id, TRIM(unnest(public.clean_and_split_person_names(artist_name))) AS name, 'artist_name' AS role 
            FROM {staging_table} WHERE artist_name IS NOT NULL AND artist_name != '' AND upload_id = :upload_id
            UNION ALL
            SELECT id AS staging_id, TRIM(unnest(public.clean_and_split_person_names(track_artist_name))) AS name, 'track_artist_name' AS role 
            FROM {staging_table} WHERE track_artist_name IS NOT NULL AND track_artist_name != '' AND upload_id = :upload_id
            UNION ALL
            SELECT id AS staging_id, TRIM(unnest(public.clean_and_split_person_names(composer))) AS name, 'composer' AS role 
            FROM {staging_table} WHERE composer IS NOT NULL AND composer != '' AND upload_id = :upload_id
            UNION ALL
            SELECT id AS staging_id, TRIM(unnest(public.clean_and_split_person_names(lyricist))) AS name, 'lyricist' AS role 
            FROM {staging_table} WHERE lyricist IS NOT NULL AND lyricist != '' AND upload_id = :upload_id
            UNION ALL
            SELECT id AS staging_id, TRIM(unnest(public.clean_and_split_person_names(authors))) AS name, 'authors' AS role 
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
    TaskProgress.emit(upload_id, f"✅ Staging persons вставлено: {count} ({elapsed:.1f} сек)")
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
    TaskProgress.emit(upload_id, f"✅ Unique persons вставлено в person: {count} ({elapsed:.1f} сек)")
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
    TaskProgress.emit(upload_id, f"✅ Right holders вставлено: {count} ({elapsed:.1f} сек)")
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
    TaskProgress.emit(upload_id, f"✅ Releases вставлено: {count} ({elapsed:.1f} сек)")
    return count


def _sync_tracks_v2_isrc(conn, upload_id, staging_table="staging_catalog_v2"):
    """5. ЗАПОЛНЯЕМ TRACK (треки)"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result_tracks = conn.execute(
        text(f"""
      
        WITH new_tracks AS (
            SELECT DISTINCT ON (sc.id)
                sc.id AS staging_id,
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
            ORDER BY sc.id
        ),
        insert_step AS (
            INSERT INTO track (isrc, label_own_code, title, title_norm_key, duration, explicit, resource_reference, meta)
            SELECT isrc, label_own_code, title, title_norm_key, duration, explicit, resource_reference, meta
          FROM new_tracks
        )
        UPDATE {staging_table}
        SET status = 'inserted' 
        FROM new_tracks
        WHERE {staging_table}.id = new_tracks.staging_id;

        """), {"upload_id": upload_id}
    )
    count = result_tracks.rowcount
    elapsed = time.time() - t0
    print(f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(upload_id, f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
    return count

def _sync_tracks_v2_label_code(conn, upload_id, staging_table="staging_catalog_v2"):
    """5. ЗАПОЛНЯЕМ TRACK (треки)"""
    task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()
    result_tracks = conn.execute(
        text(f"""
    
        WITH new_tracks AS (
 
            SELECT DISTINCT ON (sc.id)
                sc.id AS staging_id,
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
            ORDER BY sc.id
        ),
        insert_step AS (
                    INSERT INTO track (isrc, label_own_code, title, title_norm_key, duration, explicit, resource_reference, meta)
                    SELECT isrc, label_own_code, title, title_norm_key, duration, explicit, resource_reference, meta
                  FROM new_tracks
                )
        UPDATE {staging_table}
        SET status = 'inserted' 
        FROM new_tracks
        WHERE {staging_table}.id = new_tracks.staging_id;

        """), {"upload_id": upload_id}
    )
    count = result_tracks.rowcount
    elapsed = time.time() - t0
    print(f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
    TaskProgress.emit(upload_id, f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
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
    TaskProgress.emit(upload_id, f"✅ Tracks вставлено: {count} ({elapsed:.1f} сек)")
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
        WHERE sc.upload_id = :upload_id  AND sc.isrc IS NOT NULL and sc.status = 'inserted'
        
        UNION ALL

         SELECT 
            sc.id AS staging_id,
            t.id AS track_id,
            r.id AS release_id
        FROM {staging_table} sc
        JOIN track t ON t.title_norm_key = sc.track_name_norm_key   AND t.label_own_code = NULLIF(sc.right_id, '')
        LEFT JOIN release r ON r.upc = sc.upc
        WHERE sc.upload_id = :upload_id   AND (sc.isrc IS NULL ) AND NULLIF(sc.right_id, '') IS NOT NULL and sc.status = 'inserted';
        
    
        CREATE INDEX idx_tmp_map_sid ON tmp_track_map(staging_id);
        CREATE INDEX idx_tmp_map_tid ON tmp_track_map(track_id);
        ANALYZE tmp_track_map;
        """), {"upload_id": upload_id}
    )
    elapsed = time.time() - t0
    print(f"✅ tmp_track_map создана ({elapsed:.1f} сек)")
    TaskProgress.emit(upload_id, f"✅ tmp_track_map создана ({elapsed:.1f} сек)")


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
    TaskProgress.emit(upload_id, f"✅ Track_release вставлено: {count} ({elapsed:.1f} сек)")
    return count


def _sync_track_contributions_v2(conn, upload_id):
    """ЗАПОЛНЯЕМ TRACK_CONTRIBUTION напрямую из staging_person"""
    # task_id = getattr(current_task.request, 'id', None)
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
    TaskProgress.emit(upload_id, f"✅ ВСЕГО Track contributions вставлено: {total_inserted} ({elapsed:.1f} сек)")
 
   
    return total_inserted

def _update_track_contributions_from_staging(conn, upload_id):
    """ЗАПОЛНЯЕМ TRACK_CONTRIBUTION напрямую из staging_person"""
    # task_id = getattr(current_task.request, 'id', None)
    t0 = time.time()

    result = conn.execute(text("""
        delete from  track_contribution where track_id in 
        (select c.track_id from staging_catalog_v2 c where c.upload_id = :upload_id and track_id is not null and 
        c.track_id in (select track_id from staging_track_diff where upload_id = :upload_id) )
    """), {"upload_id": upload_id})

    #total_inserted = result.rowcount
   
    # Теперь нам не нужен цикл по колонкам, так как все роли уже в staging_person
    result = conn.execute(text("""
        INSERT INTO track_contribution (track_id, person_id, role)
        SELECT DISTINCT
            c.track_id,
            p.id,
            sp.role
        FROM staging_catalog_v2 c
        JOIN staging_track_diff d on d.track_id = c.track_id
        JOIN staging_person sp ON sp.staging_id = c.id  AND sp.upload_id = :upload_id
        JOIN person p ON p.norm_key_full = sp.full_name_norm_key
        WHERE c.track_id is not null
        ON CONFLICT (track_id, person_id, role) DO NOTHING;
    """), {"upload_id": upload_id})

    total_inserted = result.rowcount
    elapsed = time.time() - t0
    
    print(f"✅ ВСЕГО Track contributions вставлено: {total_inserted} ({elapsed:.1f} сек)")
    TaskProgress.emit(upload_id, f"✅ ВСЕГО Track contributions вставлено: {total_inserted} ({elapsed:.1f} сек)")
 
   
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
        TaskProgress.emit(upload_id, f"✅ В {cat_name} ({usage_code}) вставлено: {count}")

    elapsed = time.time() - t0
    print(f"🏁 ИТОГО вставлено в track_right: {track_rights_count} ({elapsed:.1f} сек)")
    TaskProgress.emit(upload_id, f"🏁 ИТОГО вставлено в track_right: {track_rights_count} ({elapsed:.1f} сек)")
    return track_rights_count


def _update_track_rights_from_staging(conn, upload_id, label_id):
    """7. ЗАПОЛНЯЕМ TRACK_RIGHT (права на треки) — с _INT/_MOB/_PUB"""

    sql = f"""
            delete from track_right where right_holder_id IN (SELECT id FROM right_holder WHERE label_id = :label_id)
                and track_id in (select track_id from staging_track_diff where upload_id = :upload_id);
        """
    conn.execute(text(sql), {"upload_id": upload_id, "label_id": label_id})
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
        SELECT DISTINCT ON (sc.track_id, rh.id, rc.id, rut.id)
            sc.track_id,
            NULL::BIGINT,
            rh.id,
            rc.id,
            rut.id,
            ROUND(CAST(NULLIF(REPLACE(sc.{share_col}, ',', '.'), '') AS NUMERIC), 2),
            sc.countries
        
        FROM staging_catalog_v2 sc
        JOIN staging_track_diff d on d.track_id = sc.track_id
        join track_label tl ON tl.track_id = sc.track_id and sc.track_id = tl.track_id
        JOIN right_holder rh ON rh.name = sc.{holder_col}
        JOIN right_category rc ON rc.name = '{cat_name}'
        JOIN right_usage_type rut ON rut.code = '{usage_code}'
        WHERE sc.{holder_col} IS NOT NULL AND sc.{holder_col} != ''
        AND sc.upload_id = :upload_id and sc.track_id IS NOT NULL
       
        ORDER BY sc.track_id, rh.id, rc.id, rut.id;
        """
        result = conn.execute(text(sql), {"upload_id": upload_id})
        count = result.rowcount
        track_rights_count += count
        print(f"✅ В {cat_name} ({usage_code}) вставлено: {count}")
        TaskProgress.emit(upload_id, f"✅ В {cat_name} ({usage_code}) вставлено: {count}")

    elapsed = time.time() - t0
    print(f"🏁 ИТОГО вставлено в track_right: {track_rights_count} ({elapsed:.1f} сек)")
    TaskProgress.emit(upload_id, f"🏁 ИТОГО вставлено в track_right: {track_rights_count} ({elapsed:.1f} сек)")
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
    TaskProgress.emit(upload_id, f"✅ Связей track_label добавлено: {count} ({elapsed:.1f} сек)")
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
    conn.execute(
        text("DELETE FROM staging_track_diff WHERE upload_id = :uid"),
        {"uid": upload_id}
    )
    elapsed = time.time() - t0
    print(f"🧹 Стейджинг v2 очищен для сессии {upload_id} ({elapsed:.1f} сек)")
    TaskProgress.emit(upload_id, f"🧹 Стейджинг v2 очищен для сессии {upload_id} ({elapsed:.1f} сек)")


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
    TaskProgress.emit(upload_id, f"✅ Right holders (v1) вставлено: {count} ({elapsed:.1f} сек)")
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
        TaskProgress.emit(upload_id, f"✅ В {cat_name} ({holder_col}) вставлено: {count}")
    elapsed = time.time() - t0
    print(f"🏁 ИТОГО вставлено в track_right (v1): {track_rights_count} ({elapsed:.1f} сек)")
    TaskProgress.emit(upload_id, f"🏁 ИТОГО вставлено в track_right (v1): {track_rights_count} ({elapsed:.1f} сек)")
    return track_rights_count


from sqlalchemy import text
from sqlalchemy.engine import Connection

from sqlalchemy import text
from sqlalchemy.engine import Connection


def _update_tracks_common_info_from_staging(conn: Connection, upload_id: str) -> None:
    """Обновляет основные поля трека (title, isrc, duration, explicit) и поле meta (jsonb) из staging_catalog_v2."""
    query = text("""
        UPDATE track t
        SET 
            title = COALESCE(NULLIF(c.track_name, ''), t.title),
            isrc = COALESCE(NULLIF(c.isrc, ''), t.isrc),
            duration = COALESCE(NULLIF(c.duration, ''), t.duration),
            explicit = CASE 
                WHEN c.explicit IS NULL OR c.explicit = '' THEN t.explicit
                WHEN LOWER(c.explicit) IN ('true', '1', 't', 'yes') THEN TRUE
                WHEN LOWER(c.explicit) IN ('false', '0', 'f', 'no') THEN FALSE
                ELSE t.explicit
            END,
            meta = COALESCE(t.meta, '{}'::jsonb) || jsonb_strip_nulls(jsonb_build_object(
                'genre', NULLIF(c.genre_name, ''),
                'track_number', NULLIF(c.track_number, '')
            ))
        FROM (
            SELECT DISTINCT ON (c.track_id)
                c.track_id,
                c.track_name,
                c.isrc,
                c.duration,
                c.explicit,
                c.genre_name,
                c.track_number
            FROM staging_catalog_v2 c
            JOIN staging_track_diff d ON d.track_id = c.track_id
            WHERE c.track_id IS NOT NULL 
              AND d.upload_id = :upload_id
        ) c
        WHERE t.id = c.track_id;
    """)
    conn.execute(query, {"upload_id": upload_id})


def get_catalog_deleted_tracks(conn: Connection, label_id: int, upload_id: str) -> list:
    query = text("""
        SELECT 
            t.id,
            t.isrc,
            t.title,
            t.artist,
            'DELETED' AS diff_type  -- Пометка типа изменения для сетки/стилей
        FROM track t
        JOIN track_label tl ON tl.track_id = t.id
        WHERE tl.label_id = :label_id  
          AND NOT EXISTS (
            SELECT 1
            FROM staging_catalog_v2 s
            WHERE s.track_id = t.id AND s.upload_id = :upload_id
          )
    """)
    
    # .mappings().all() возвращает список словарей [{ 'id': 1, 'isrc': '...', ... }]
    result = conn.execute(query, {"label_id": label_id, "upload_id": upload_id}).mappings().all()
    
    return [dict(row) for row in result]

def create_catalog_upload(
    conn: Connection,
    upload_id: str,
    label_id: int,
    user_id: int,
    filename: str
   
) -> None:
    """Создает новую запись о загрузке каталога со статусом PROCESSING."""
    query = text("""
        INSERT INTO catalog_upload (upload_id, label_id, user_id, filename, status, created_at)
        VALUES (:upload_id, :label_id, :user_id, :filename, 'PROCESSING', CURRENT_TIMESTAMP)
    """)
    conn.execute(
        query,
        {
            "upload_id": upload_id,
            "label_id": label_id,
            "user_id": user_id,
            "filename": filename
          
        }
    )
    return None
def get_processing_upload_id(conn: Connection, label_id: int) -> Optional[str]:
    """Возвращает upload_id в статусе PROCESSING для указанного лейбла (или None, если не найден)."""
    query = text("""
        SELECT upload_id 
        FROM catalog_upload 
        WHERE label_id = :label_id AND status = 'PROCESSING' 
        ORDER BY created_at DESC 
        LIMIT 1
    """)
    result = conn.execute(query, {"label_id": label_id}).scalar()
    return result
def update_upload_status(conn: Connection, upload_id: str, status: str) -> None:
    """Обновляет статус записи в catalog_upload по upload_id."""
    query = text("""
        UPDATE catalog_upload
        SET status = :status
        WHERE upload_id = :upload_id
    """)
    conn.execute(query, {"upload_id": upload_id, "status": status})
def refresh_track_materialized_views(conn: Connection) -> None:
    TaskProgress.emit(upload_id, f"✅ Начинаем обновление представлений.") 
    conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_extended; "))
    conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights_prev; "))
    conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights; "))
       
    print(f"🏁 Представления обновлены.")
    TaskProgress.emit(upload_id, f"✅ Загружка каталога завершена полностью.")  