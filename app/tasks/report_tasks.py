import os
import polars as pl
from sqlalchemy import create_engine, text
from core.celery_app import celery_app
from celery import current_task
from core.constants import RightCategory, FindingSource
from .utils import clean_null_bytes
from services.broadcaster import TaskProgress
import uuid
import time
from typing import Optional, List
import re
import xlsxwriter

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)



def _match_by_name(match_type, partner_id, right_category_id, right_usage_type_id, month, year, upload_id):
    """
    Поиск и вставка в report по track_name + person.
    match_type определяет тип сравнения:
    AUTHOR — сравнение по authors (роли authors/composer/lyricist).
    RELATED — сравнение по artist_name (роль artist_name).
    right_category_id — значение, записываемое в таблицу report.
    Возвращает (inserted, deleted).
    """
    if match_type == RightCategory.AUTHOR:
        staging_col = "authors"
        roles = "('authors', 'composer', 'lyricist')"
        finding_source = FindingSource.NAME_AUTHOR
        label = "NAME+AUTHOR"
    else:
        staging_col = "artist_name"
        roles = "('artist_name')"
        finding_source = FindingSource.NAME_ARTIST
        label = "NAME+ARTIST"

    insert_sql = text(f"""
        INSERT INTO staging_report_ids (staging_id, track_id, finding_source, upload_id)
        SELECT distinct s.id, t.id, :finding_source, :uid
        FROM staging_report_agg s
        JOIN track t ON t.title = s.track_name
        WHERE  s.{staging_col} IS NOT NULL AND s.{staging_col} != '' and upload_id = :uid
        AND s.isfound = FALSE
        AND EXISTS (
            SELECT 1
            FROM track_contribution tc
            JOIN person p ON p.id = tc.person_id
            WHERE tc.track_id = t.id
                AND tc.role IN {roles}
                AND p.full_name = ANY(clean_and_split(s.{staging_col}))
        );
    """)

    mark_found_sql = text("""
        UPDATE staging_report_agg s SET isfound = TRUE
        WHERE s.isfound = FALSE and s.upload_id = :uid
        AND EXISTS (SELECT 1 FROM staging_report_ids si WHERE si.staging_id = s.id and si.upload_id = :uid);
    """)

    params = {
        "finding_source": finding_source,
        "uid": upload_id
    }

    with engine.begin() as connection:
        result = connection.execute(insert_sql, params)
        inserted = result.rowcount
    print(f"✅ Данные добавлены в staging_report_ids по {label}. Записей: {inserted}")
    TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Данные добавлены в staging_report_ids по {label}. Записей: {inserted}")
    
    with engine.begin() as connection:
        mark_result = connection.execute(mark_found_sql, params)
        marked = mark_result.rowcount
    print(f"✅ Помечено как найденные в staging_report_agg по {label}: {marked}")
    TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Помечено как найденные в staging_report_agg по {label}: {marked}")

    return inserted, marked


@celery_app.task(name="process_report_file")
def process_report_file(file_path: str, upload_id: str):
    df = None
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File not found"}

    try:
        df = pl.read_excel(file_path, read_options={"skip_rows":0})

        #df = df.select(pl.all().exclude(df.columns[14:]))

        df = df.filter(~pl.all_horizontal(pl.all().is_null()))

        db_columns = [
            "row_number", "label_own_code", "isrc", "track_name",
            "artist_name", "composer", "lyricist", "authors",
            "author_share_pct", "related_share_pct", "play_count",
            "payout_amount", "price_per_play", "service_name"
        ]

        total_rows = len(df)
        chunk_size = 50000

        print(f"РЕАЛЬНЫЕ ИМЕНА ИЗ EXCEL: {df.columns}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"РЕАЛЬНЫЕ ИМЕНА ИЗ EXCEL: {df.columns}")


        for i in range(0, total_rows, chunk_size):
            chunk = df.slice(i, chunk_size)
            
            chunk.columns = db_columns

            chunk = chunk.select(db_columns)
            
            print(f"DEBUG: Chunk shape: {chunk.shape}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"DEBUG: Chunk shape: {chunk.shape}")
            print(f"DEBUG: Chunk columns: {chunk.columns}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"DEBUG: Chunk columns: {chunk.columns}")
            print(f"DEBUG: Chunk dtypes: {chunk.dtypes}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"DEBUG: Chunk dtypes: {chunk.dtypes}")
            if len(chunk) > 0:
                print(f"DEBUG: First row: {chunk.row(0)}")
                TaskProgress.emit(getattr(current_task.request, 'id', None), f"DEBUG: First row: {chunk.row(0)}")
            
            chunk = chunk.with_columns([
                pl.col("*").cast(pl.Utf8).fill_null("")
            ])

            chunk = clean_null_bytes(chunk)

            print(f"DEBUG: After cleaning dtypes: {chunk.dtypes}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"DEBUG: After cleaning dtypes: {chunk.dtypes}")
            if len(chunk) > 0:
                print(f"DEBUG: First row after cleaning: {chunk.row(0)}")
                TaskProgress.emit(getattr(current_task.request, 'id', None), f"DEBUG: First row after cleaning: {chunk.row(0)}")

            print(f"DEBUG: Column count: {len(chunk.columns)}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"DEBUG: Column count: {len(chunk.columns)}")
            print(f"DEBUG: Shape: {chunk.shape}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"DEBUG: Shape: {chunk.shape}")

            chunk = chunk.with_columns(pl.lit(upload_id).alias("upload_id"))
            chunk.write_database(
                table_name="staging_report",
                connection=DATABASE_URL,
                if_table_exists="append",
                engine="adbc"
            )
            print(f"📦 Загружен батч отчёта: {i} - {i + len(chunk)}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"📦 Загружен батч отчёта: {i} - {i + len(chunk)}")

        if os.path.exists(file_path):
            os.remove(file_path)
            
        return {"status": "success", "total_rows": total_rows}

    except Exception as e:
        print(f"❌ Ошибка воркера (отчёт): {str(e)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка воркера (отчёт): {str(e)}")
        return {"status": "error", "message": str(e)}



@celery_app.task(name="insert_data_into_final_report_table")
def insert_data_into_final_report_table(partner_id: int, right_category_id: int, right_usage_type_id: int, month: int, year: int, upload_id: str):
    """
    Задача для переноса данных из staging_report в итоговую таблицу report.
    После вставки экспортирует данные в Excel с информацией о треках и правах.
    """
    try:
        total_rows_affected = 0      

        # === Шаг 1: Поиск по ISRC + label_own_code ===
        insert_by_isrc_sql = text("""
            INSERT INTO staging_report_ids (staging_id, track_id, finding_source, upload_id)
            SELECT distinct s.id, t.id, :finding_source, :uid
            FROM staging_report_agg s
            JOIN track t ON s.isrc = t.isrc and s.label_own_code = t.label_own_code
            WHERE s.isrc IS NOT NULL AND s.isfound = FALSE AND s.upload_id = :uid;
        """)
        with engine.begin() as connection:
            result = connection.execute(insert_by_isrc_sql, {
                "finding_source": FindingSource.ISRC__LABEL_CODE,
                "upload_id": upload_id,
                "uid": upload_id
            })
            rows_affected = result.rowcount
            total_rows_affected += rows_affected

        print(f"✅ Шаг 1: Найдено совпадений по ISRC + label_own_code: {rows_affected}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Шаг 1: Найдено совпадений по ISRC + label_own_code: {rows_affected}")


        mark_found_sql = text("""
            UPDATE staging_report_agg s SET isfound = TRUE
            WHERE s.isfound = FALSE and s.upload_id = :uid
            AND EXISTS (SELECT 1 FROM staging_report_ids si WHERE si.staging_id = s.id);
        """)
        with engine.begin() as connection:
            mark_result = connection.execute(mark_found_sql, {"uid": upload_id})
            print(f"✅ Шаг 2: Помечено как найденные в staging_report_agg по ISRC: {mark_result.rowcount}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Шаг 2: Помечено как найденные в staging_report_agg по ISRC: {mark_result.rowcount}")


         # === Шаг 1.1: Поиск по ISRC ===
        insert_by_isrc_sql = text("""
            INSERT INTO staging_report_ids (staging_id, track_id, finding_source, upload_id)
            SELECT distinct s.id, t.id, :finding_source, :uid
            FROM staging_report_agg s
            JOIN track t ON s.isrc = t.isrc
            WHERE s.isrc IS NOT NULL AND s.isfound = FALSE AND s.upload_id = :uid;
        """)
        with engine.begin() as connection:
            result = connection.execute(insert_by_isrc_sql, {
                "finding_source": FindingSource.ISRC,
                "upload_id": upload_id,
                "uid": upload_id
            })
            rows_affected = result.rowcount
            total_rows_affected += rows_affected
        print(f"✅ Шаг 1: Найдено совпадений по ISRC: {rows_affected}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Шаг 1: Найдено совпадений по ISRC: {rows_affected}")



        # === Шаг 2: Пометка найденных по ISRC в staging_report_agg ===
        mark_found_sql = text("""
            UPDATE staging_report_agg s SET isfound = TRUE
            WHERE s.isfound = FALSE and s.upload_id = :uid
            AND EXISTS (SELECT 1 FROM staging_report_ids si WHERE si.staging_id = s.id);
        """)

        with engine.begin() as connection:
            mark_result = connection.execute(mark_found_sql, {"uid": upload_id})
            print(f"✅ Шаг 2: Помечено как найденные в staging_report_agg по ISRC: {mark_result.rowcount}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Шаг 2: Помечено как найденные в staging_report_agg по ISRC: {mark_result.rowcount}")



        # === Шаг 3: Поиск по label_own_code ===
        insert_by_label_sql = text("""
            INSERT INTO staging_report_ids (staging_id, track_id, finding_source, upload_id)
            SELECT  DISTINCT s.id, t.id, :finding_source, :uid
            FROM staging_report_agg s
            JOIN track t ON s.label_own_code = t.label_own_code
            WHERE s.label_own_code IS NOT NULL AND s.isfound = FALSE and s.upload_id = :uid;
        """)
        with engine.begin() as connection:
            result = connection.execute(insert_by_label_sql, {
                "finding_source": FindingSource.LABEL_OWN_CODE,
                "upload_id": upload_id,
                "uid": upload_id
            })
            rows_affected = result.rowcount
            total_rows_affected += rows_affected

        print(f"✅ Шаг 3: Найдено совпадений по label_own_code: {rows_affected}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Шаг 3: Найдено совпадений по label_own_code: {rows_affected}")

        mark_found_sql = text("""
            UPDATE staging_report_agg s SET isfound = TRUE
            WHERE s.isfound = FALSE and s.upload_id = :uid
            AND EXISTS (SELECT 1 FROM staging_report_ids si WHERE si.staging_id = s.id);
        """)

        with engine.begin() as connection:
            mark_result = connection.execute(mark_found_sql, {"uid": upload_id})
            print(f"✅ Шаг 2: Помечено как найденные в staging_report_agg по LABEL_OWN_CODE: {mark_result.rowcount}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Шаг 2: Помечено как найденные в staging_report_agg по LABEL_OWN_CODE: {mark_result.rowcount}")



      

        # === Шаг 5: Поиск по track_name + authors (author/composer/lyricist) ===
        inserted, deleted = _match_by_name(RightCategory.AUTHOR, partner_id, right_category_id, right_usage_type_id, month, year, upload_id)
        total_rows_affected += inserted

        # === Шаг 6: Поиск по track_name + artist_name ===
        inserted, deleted = _match_by_name(RightCategory.RELATED, partner_id, right_category_id, right_usage_type_id, month, year, upload_id)
        total_rows_affected += inserted


        normalize_staging_report_agg(upload_id)

        # === Шаг 7: Поиск по track_name + authors (author/composer/lyricist) ===
        inserted, deleted = _match_by_normalized_name(RightCategory.AUTHOR, partner_id, right_category_id, right_usage_type_id, month, year, "=", "=",  upload_id)
        total_rows_affected += inserted

        # === Шаг 8: Поиск по track_name + artist_name ===
        inserted, deleted = _match_by_normalized_name(RightCategory.RELATED, partner_id, right_category_id, right_usage_type_id, month, year, "=", "=", upload_id)
        total_rows_affected += inserted

        # === Шаг 7: Поиск по track_name + authors (author/composer/lyricist) ===
        inserted, deleted = _match_by_normalized_name(RightCategory.AUTHOR, partner_id, right_category_id, right_usage_type_id, month, year, "=", "like", upload_id)
        total_rows_affected += inserted

        # === Шаг 8: Поиск по track_name + artist_name ===
        inserted, deleted = _match_by_normalized_name(RightCategory.RELATED, partner_id, right_category_id, right_usage_type_id, month, year, "=", "like", upload_id)
        total_rows_affected += inserted

            # === Шаг 7: Поиск по track_name + authors (author/composer/lyricist) ===
        inserted, deleted = _match_by_normalized_name(RightCategory.AUTHOR, partner_id, right_category_id, right_usage_type_id, month, year, "like", "=", upload_id)
        total_rows_affected += inserted

        # === Шаг 8: Поиск по track_name + artist_name ===
        inserted, deleted = _match_by_normalized_name(RightCategory.RELATED, partner_id, right_category_id, right_usage_type_id, month, year, "like", "=", upload_id)
        total_rows_affected += inserted



        inserted, deleted = _match_by_normalized_name(RightCategory.AUTHOR, partner_id, right_category_id, right_usage_type_id, month, year, "partly", "=", upload_id)
        total_rows_affected += inserted

        # === Шаг 8: Поиск по track_name + artist_name ===
        inserted, deleted = _match_by_normalized_name(RightCategory.RELATED, partner_id, right_category_id, right_usage_type_id, month, year, "partly", "=", upload_id)
        total_rows_affected += inserted

    


    






        rows_affected = total_rows_affected
        print(f"✅ Итого найдено совпадений в staging_report_ids: {total_rows_affected}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Итого найдено совпадений в staging_report_ids: {total_rows_affected}")

        # === Финальный шаг: перенос данных из staging_report_ids в report ===
        final_insert_sql = text("""
            INSERT INTO report (
                partner_id, right_category_id, right_usage_type_id,
                report_month, report_year,  payout_amount,  upload_id
            )
            SELECT
                :partner_id,
                :right_category_id,
                :right_usage_type_id,
                :month,
                :year,
                sum(s.payout_amount),
                :uid
            FROM staging_report_agg  s
            where  s.upload_id = :uid ;
        """)

        with engine.begin() as connection:
            result = connection.execute(final_insert_sql, {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year,
                "uid": upload_id
            })
            rows_affected = result.rowcount
        print(f"✅ Данные перенесены в report из staging_report_ids. Записей: {rows_affected}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Данные перенесены в report из staging_report_ids. Записей: {rows_affected}")

        # Экспорт данных в Excel
        export_result = export_report_to_excel(partner_id, right_category_id, right_usage_type_id, month, year, upload_id)
        if export_result.get("status") != "success":
            return {"status": "error", "message": export_result.get("message")}

        return {
            "status": "success",
            "report_records_added": rows_affected,
            "rows_exported": export_result.get("rows_exported"),
            "output_file": export_result.get("output_file"),
        }

    except Exception as e:
        print(f"❌ Ошибка при переносе данных в report: {str(e)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка при переносе данных в report: {str(e)}")
        return {"status": "error", "message": str(e)}


@celery_app.task(name="export_report_to_excel")
def export_report_to_excel(partner_id: int, right_category_id: int, right_usage_type_id: int, month: int, year: int, upload_id: str = None):
    """
    Экспорт данных из staging_report_ids / staging_report_agg в Excel-файл
    с информацией о треках и правах.
    """
    try:
        print("📤 Начинаем экспорт отчёта в Excel...")
        TaskProgress.emit(getattr(current_task.request, 'id', None), "📤 Начинаем экспорт отчёта в Excel...")
        base_query = text("""
        SELECT DISTINCT ON (s.row_number, s.id)
            s.id AS staging_id,
            s.row_number AS "№ строки",
            s.isrc AS "Отчет ISRC",
            s.label_own_code AS "Отчет код лейбла",
            s.track_name AS "Отчет название трека",
            s.artist_name AS "Отчет исполнитель",
            s.authors AS "Отчет авторы",
            s.service_name AS "Отчет сервис",
            t.label_own_code AS "Код лейбла",
            t.isrc AS "Код ISRC",
            t.title AS "Название трека",
            (SELECT string_agg(DISTINCT p.full_name, ', ')
            FROM track_contribution tc JOIN person p ON p.id = tc.person_id
            WHERE tc.track_id = t.id AND tc.role = 'artist_name'
            ) AS "Исполнитель",
            (SELECT string_agg(DISTINCT p.full_name, ', ')
            FROM track_contribution tc JOIN person p ON p.id = tc.person_id
            WHERE tc.track_id = t.id AND tc.role = 'composer'
            ) AS "Автор музыки",
            (SELECT string_agg(DISTINCT p.full_name, ', ')
            FROM track_contribution tc JOIN person p ON p.id = tc.person_id
            WHERE tc.track_id = t.id AND tc.role = 'lyricist'
            ) AS "Автор текста",
            (SELECT string_agg(DISTINCT p.full_name, ', ')
            FROM track_contribution tc JOIN person p ON p.id = tc.person_id
            WHERE tc.track_id = t.id AND tc.role = 'authors'
            ) AS "Авторы",
            s.play_count AS "Кол-во прослушиваний",
            s.payout_amount AS "Сумма выплат",
            s.price_per_play AS "Цена за прослушивание",
            fs.code AS "Источник совпадения"
        FROM staging_report_agg s
        LEFT JOIN staging_report_ids si ON si.staging_id = s.id and s.upload_id = :uid  AND si.upload_id = :uid
        LEFT JOIN track t ON t.id = si.track_id
        LEFT JOIN finding_source fs ON fs.id = si.finding_source
       
        ORDER BY s.row_number ASC, s.id;
        """)

        rights_query = text("""
        SELECT DISTINCT
            si.staging_id,
            rc.name AS category,
            rh.name AS right_holder_name,
            tr.share_percentage,
            rut.code AS right_usage_type_code
        FROM staging_report_ids si
        JOIN track_right tr ON tr.track_id = si.track_id
        JOIN right_category rc ON rc.id = tr.right_category_id
        JOIN right_holder rh ON rh.id = tr.right_holder_id
        JOIN right_usage_type rut ON rut.id = tr.right_usage_type_id
        WHERE si.upload_id = :uid
        ORDER BY si.staging_id, rc.name, rut.code;
        """)

        # Запрос для поиска ДОПОЛНИТЕЛЬНЫХ прав по базовому коду (без тире)
        extended_rights_query = text("""
            SELECT DISTINCT
                si.staging_id,
                rc.name AS category,
                rh.name AS right_holder_name,
                tr.share_percentage,
                rut.code AS right_usage_type_code
            FROM staging_report_ids si
            JOIN track t_orig ON t_orig.id = si.track_id
            JOIN track t_all ON split_part(t_all.label_own_code, '-', 1) = split_part(t_orig.label_own_code, '-', 1)
            JOIN track_right tr ON tr.track_id = t_all.id
            JOIN right_category rc ON rc.id = tr.right_category_id
            JOIN right_holder rh ON rh.id = tr.right_holder_id
            JOIN right_usage_type rut ON rut.id = tr.right_usage_type_id
            WHERE t_all.id != si.track_id AND si.upload_id = :uid
        """)



        with engine.connect() as conn:
            # Выполняем запросы с параметрами и конвертируем в Polars
            result = conn.execute(base_query, {"uid": upload_id})
            df_base = pl.DataFrame(result.fetchall(), schema=result.keys(), infer_schema_length=None)
            
            result = conn.execute(rights_query, {"uid": upload_id})
            df_rights = pl.DataFrame(result.fetchall(), schema=result.keys(), infer_schema_length=None)
            
            result = conn.execute(extended_rights_query, {"uid": upload_id})
            df_ext = pl.DataFrame(result.fetchall(), schema=result.keys(), infer_schema_length=None)



            meta_row = conn.execute(text("""
                SELECT
                    COALESCE(p.code, p.id::TEXT) AS partner_code,
                    rc.name AS right_category_name,
                    rut.code AS right_usage_type_code
                FROM partners p
                JOIN right_category rc ON rc.id = :right_category_id
                JOIN right_usage_type rut ON rut.id = :right_usage_type_id
                WHERE p.id = :partner_id
            """), {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
            }).fetchone()

        partner_code = meta_row.partner_code if meta_row else str(partner_id)
        right_category_name = meta_row.right_category_name if meta_row else str(right_category_id)
        right_usage_type_code = meta_row.right_usage_type_code if meta_row else str(right_usage_type_id)

        if len(df_ext) > 0:
            if len(df_rights) > 0:
                existing_rights = df_rights.select(["staging_id", "category", "right_usage_type_code"]).unique()
                df_ext_filtered = df_ext.join(
                    existing_rights,
                    on=["staging_id", "category", "right_usage_type_code"],
                    how="anti"
                )
            else:
                df_ext_filtered = df_ext

            df_rights_all = pl.concat([
                df_rights,
                df_ext_filtered
            ], how="vertical")

            df_rights_all = df_rights_all.unique(
                subset=["staging_id", "category", "right_holder_name", "right_usage_type_code"]
            )
        else:
            df_rights_all = df_rights

        if len(df_rights_all) > 0:
            df_rights_all = df_rights_all.with_columns(
                pl.int_range(1, pl.len() + 1)
                .over(["staging_id", "category", "right_usage_type_code"])
                .alias("rn")
            )

            category_map = {"Author": "авторские", "Related": "смежные"}
            groups = df_rights_all.select(["category", "right_usage_type_code"]).unique().sort(["category", "right_usage_type_code"])

            for row in groups.iter_rows(named=True):
                cat = row["category"]
                rut_code = row["right_usage_type_code"]
                cat_label = category_map.get(cat, cat)

                df_group = df_rights_all.filter(
                    (pl.col("category") == cat) & (pl.col("right_usage_type_code") == rut_code)
                )

                max_rn = df_group.select(pl.col("rn").max()).item() if len(df_group) > 0 else 0

                for i in range(1, (max_rn or 0) + 1):
                    suffix = f" {i}" if max_rn > 1 else ""

                    group_i = df_group.filter(pl.col("rn") == i).select([
                        pl.col("staging_id"),
                        pl.col("share_percentage").alias(f"Доля {cat_label} прав {rut_code}{suffix}, %"),
                        pl.col("right_holder_name").alias(f"Правообладатель ({cat_label}) {rut_code}{suffix}"),
                    ])
                    df_base = df_base.join(group_i, on="staging_id", how="left")

        df = df_base.drop("staging_id")

        # Сортировка по row_number если данные без группировки
        if "№ строки" in df.columns and df["№ строки"].drop_nulls().len() > 0:
            df = df.sort("№ строки")
        else:
            df = df.drop("№ строки")

        storage_dir = "/app/storage"
        os.makedirs(storage_dir, exist_ok=True)
        filename = f"report_{year}_{month}_{partner_code}_{right_category_name}_{right_usage_type_code}.xlsx"
        output_path = os.path.join(storage_dir, filename)
        df.write_excel(output_path)

        print(f"✅ Отчёт экспортирован в файл: {output_path}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Отчёт экспортирован в файл: {output_path}")
        print(f"📊 Всего строк в файле: {len(df)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"📊 Всего строк в файле: {len(df)}")

        return {
            "status": "success",
            "rows_exported": len(df),
            "output_file": output_path,
        }

    except Exception as e:
        print(f"❌ Ошибка при экспорте отчёта в Excel: {str(e)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка при экспорте отчёта в Excel: {str(e)}")
        return {"status": "error", "message": str(e)}



@celery_app.task(name="process_full_report_pipeline")
def process_full_report_pipeline(file_path: str, partner_id: int, right_category_id: int, right_usage_type_id: int, month: int, year: int, group_data: bool = True):
    """
    Оркестратор: последовательно выполняет весь пайплайн обработки отчёта.
    Каждая задача запускается только при успехе предыдущей.
    """
    upload_id = str(uuid.uuid4())
    steps_completed = []

    # === Шаг 0: Очистка staging таблиц ===
    try:
        print("🧹 Шаг 0: Очистка staging_report и staging_report_agg...")

        delete_sql = text("""
            DELETE FROM report
            WHERE partner_id = :partner_id
            AND right_category_id = :right_category_id
            AND right_usage_type_id = :right_usage_type_id
            AND report_month = :month
            AND report_year = :year
            RETURNING upload_id;
        """)
        with engine.begin() as connection:
            delete_result = connection.execute(delete_sql, {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year,
            })
            
            deleted_upload_ids = [row[0] for row in delete_result.fetchall()]
    
            print(f"Удалены записи с upload_id: {deleted_upload_ids}")
            print(f"🗑️ Удалено старых записей из report: {delete_result.rowcount}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"🗑️ Удалено старых записей из report: {delete_result.rowcount}")

    

        # === Создание/очистка staging_report_ids ===
        with engine.begin() as connection:
            connection.execute(text("delete from staging_report_agg where upload_id  = ANY(:uids);"), {"uids": deleted_upload_ids})
        with engine.begin() as connection:
            connection.execute(text("delete from staging_report_ids where upload_id  = ANY(:uids);"), {"uids": deleted_upload_ids})    
        print("✅ Таблица staging_report_ids готова и очищена")
        TaskProgress.emit(getattr(current_task.request, 'id', None), "✅ Таблица staging_report_ids готова и очищена")




        TaskProgress.emit(getattr(current_task.request, 'id', None), "🧹 Шаг 0: Очистка staging_report и staging_report_agg...")
        with engine.begin() as connection:
            _cleanup_staging_report_tables(connection, upload_id)
        print("✅ Шаг 0 завершён: staging таблицы очищены")
        TaskProgress.emit(getattr(current_task.request, 'id', None), "✅ Шаг 0 завершён: staging таблицы очищены")

        steps_completed.append("clean_staging")
    except Exception as e:
        print(f"❌ Шаг 0 (очистка staging): {e}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Шаг 0 (очистка staging): {e}")
        return {"status": "error", "step": "clean_staging", "message": str(e), "steps_completed": steps_completed}

    try:

        # === Шаг 1: Загрузка и парсинг файла ===
        print("📥 Шаг 1: Загрузка и парсинг файла (process_report_file)...")
        TaskProgress.emit(getattr(current_task.request, 'id', None), "📥 Шаг 1: Загрузка и парсинг файла (process_report_file)...")
        result = process_report_file(file_path, upload_id)

        if result.get("status") != "success":
            print(f"❌ Шаг 1 (process_report_file) завершился с ошибкой: {result.get('message')}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Шаг 1 (process_report_file) завершился с ошибкой: {result.get('message')}")
            return {"status": "error", "step": "process_report_file", "message": result.get("message"), "steps_completed": steps_completed}
        print(f"✅ Шаг 1 завершён: process_report_file — загружено строк: {result.get('total_rows')}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Шаг 1 завершён: process_report_file — загружено строк: {result.get('total_rows')}")
        steps_completed.append("process_report_file")



        # === Шаг 3: Группировка данных ===
        print(f"📊 Шаг 3: Группировка данных (group_report_data, group_data={group_data})...")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"📊 Шаг 3: Группировка данных (group_report_data, group_data={group_data})...")

        result = group_report_data(group_data, upload_id)

        if result.get("status") != "success":
            print(f"❌ Шаг 3 (group_report_data) завершился с ошибкой: {result.get('message')}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Шаг 3 (group_report_data) завершился с ошибкой: {result.get('message')}")
            return {"status": "error", "step": "group_report_data", "message": result.get("message"), "steps_completed": steps_completed}
        print(f"✅ Шаг 3 завершён: group_report_data — агрегировано: {result.get('rows_aggregated')}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Шаг 3 завершён: group_report_data — агрегировано: {result.get('rows_aggregated')}")
        steps_completed.append("group_report_data")

        # === Шаг 4: Проверка sum(payout_amount) ===
        try:
            print("🔍 Шаг 4: Проверка sum(payout_amount) staging_report == staging_report_agg...")
            TaskProgress.emit(getattr(current_task.request, 'id', None), "🔍 Шаг 4: Проверка sum(payout_amount) staging_report == staging_report_agg...")
            with engine.connect() as connection:
                row = connection.execute(text("""
                    SELECT
                        (SELECT COALESCE(SUM(COALESCE(NULLIF(REPLACE(payout_amount, ',', '.'), ''), '0')::NUMERIC(20,8)), 0) FROM staging_report WHERE upload_id = :uid) AS sum_staging,
                        (SELECT COALESCE(SUM(payout_amount), 0) FROM staging_report_agg WHERE upload_id = :uid) AS sum_agg
                """), {"uid": upload_id}).fetchone()
                sum_staging = row.sum_staging
                sum_agg = row.sum_agg
            if sum_staging != sum_agg:
                msg = f"Суммы payout_amount не совпадают: staging_report={sum_staging}, staging_report_agg={sum_agg}"
                print(f"❌ Шаг 4: {msg}")
                TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Шаг 4: {msg}")
                return {"status": "error", "step": "verify_payout_amount", "message": msg, "steps_completed": steps_completed, "sum_staging": str(sum_staging), "sum_agg": str(sum_agg)}
            print(f"✅ Шаг 4 завершён: суммы совпадают ({sum_staging})")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Шаг 4 завершён: суммы совпадают ({sum_staging})")
            steps_completed.append("verify_payout_amount")
        except Exception as e:
            print(f"❌ Шаг 4 (проверка payout_amount): {e}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Шаг 4 (проверка payout_amount): {e}")
            return {"status": "error", "step": "verify_payout_amount", "message": str(e), "steps_completed": steps_completed}

        # === Шаг 5: Перенос данных в итоговую таблицу report ===
        print("📝 Шаг 5: Перенос данных в итоговую таблицу (insert_data_into_final_report_table)...")
        TaskProgress.emit(getattr(current_task.request, 'id', None), "📝 Шаг 5: Перенос данных в итоговую таблицу (insert_data_into_final_report_table)...")
        result = insert_data_into_final_report_table(partner_id, right_category_id, right_usage_type_id, month, year, upload_id)
        if result.get("status") != "success":
            print(f"❌ Шаг 5 (insert_data_into_final_report_table) завершился с ошибкой: {result.get('message')}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Шаг 5 (insert_data_into_final_report_table) завершился с ошибкой: {result.get('message')}")
            return {"status": "error", "step": "insert_data_into_final_report_table", "message": result.get("message"), "steps_completed": steps_completed}
        print(f"✅ Шаг 5 завершён: insert_data_into_final_report_table — записей: {result.get('report_records_added')}, экспортировано: {result.get('rows_exported')}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Шаг 5 завершён: insert_data_into_final_report_table — записей: {result.get('report_records_added')}, экспортировано: {result.get('rows_exported')}")
        steps_completed.append("insert_data_into_final_report_table")

        print("🎉 Пайплайн завершён успешно!")
        TaskProgress.emit(getattr(current_task.request, 'id', None), "🎉 Пайплайн завершён успешно!")
        return {
            "status": "success",
            "steps_completed": steps_completed,
            "final_result": result
        }
    except Exception as e:
        print(f"❌ Пайплайн прерван на шаге {steps_completed[-1] if steps_completed else 'начало'}: {e}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка: {e}")
        return {
            "status": "error",
            "step": steps_completed[-1] if steps_completed else "setup",
            "message": str(e),
            "steps_completed": steps_completed
        }
    finally:
  
        print(f"🧹 Финальная очистка staging-таблиц для сессии {upload_id}...")
        with engine.begin() as connection:
            _cleanup_staging_report_tables(connection, upload_id)
        print("✅ Staging-таблицы очищены")    


@celery_app.task(name="group_report_data")
def group_report_data(group_data: bool = True, upload_id: str  = None):
    """
    Задача для группировки данных отчёта и сохранения в staging_report_agg,
    а затем экспорта в файл report_avg.xlsx.
    group_data=True — группировка с агрегацией (row_number пустой).
    group_data=False — без группировки, row_number заполняется.
    """
    try:
        with engine.begin() as connection:
            print(f"📋 Начинаем {'группировку' if group_data else 'перенос без группировки'} данных отчёта...")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"📋 Начинаем {'группировку' if group_data else 'перенос без группировки'} данных отчёта...")
            
        
      
            
            truncate_sql = text("DELETE FROM staging_report_agg where upload_id = :uid;")
            connection.execute(truncate_sql, {"uid": upload_id})
            print("✅ Таблица staging_report_agg очищена")
            TaskProgress.emit(getattr(current_task.request, 'id', None), "✅ Таблица staging_report_agg очищена")

            if group_data:
                insert_agg_sql = text("""
                    INSERT INTO staging_report_agg (
                        upload_id,
                        label_own_code,
                        isrc,
                        track_name,
                        artist_name,
                        authors,
                        service_name,
                        play_count,
                        payout_amount,
                        price_per_play
                    )
                    SELECT 
                        :uid,
                        label_own_code,
                        isrc,   
                        track_name,
                        artist_name,
                        concat_ws(', ', NULLIF(TRIM(authors), ''), NULLIF(TRIM(composer), ''), NULLIF(TRIM(lyricist), '')) AS authors,
                        service_name,
                        SUM(COALESCE(NULLIF(play_count, '')::INT, 0)) as total_plays,
                        SUM(COALESCE(NULLIF(payout_amount, '')::NUMERIC(20, 8), 0)) as total_payout,
                        AVG(NULLIF(COALESCE(NULLIF(price_per_play, '')::NUMERIC(20, 8), 0), 0)) as avg_price
                    FROM staging_report
                    WHERE upload_id = :uid
                    GROUP BY label_own_code, isrc, track_name, artist_name,
                                concat_ws(', ', NULLIF(TRIM(authors), ''), NULLIF(TRIM(composer), ''), NULLIF(TRIM(lyricist), '')),
                                service_name;
                    """)
            else:
                insert_agg_sql = text("""
                    INSERT INTO staging_report_agg (
                        upload_id,
                        row_number,
                        label_own_code,
                        isrc,
                        track_name,
                        artist_name,
                        authors,
                        service_name,
                        play_count,
                        payout_amount,
                        price_per_play
                    )
                    SELECT 
                        :uid,
                        COALESCE(NULLIF(row_number, '')::INT, 0),
                        label_own_code,
                        isrc,   
                        track_name,
                        artist_name,
                        concat_ws(', ', NULLIF(TRIM(authors), ''), NULLIF(TRIM(composer), ''), NULLIF(TRIM(lyricist), '')) AS authors,
                        service_name,
                        COALESCE(NULLIF(play_count, '')::INT, 0),
                        COALESCE(NULLIF(payout_amount, '')::NUMERIC(20, 8), 0),
                        NULLIF(COALESCE(NULLIF(price_per_play, '')::NUMERIC(20, 8), 0), 0)
                    FROM staging_report where upload_id = :uid
                    ORDER BY COALESCE(NULLIF(row_number, '')::INT, 0);
                    """)
            
            result = connection.execute(insert_agg_sql, {"uid": upload_id})
            rows_inserted = result.rowcount
            print(f"✅ Агрегировано и вставлено записей: {rows_inserted}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Агрегировано и вставлено записей: {rows_inserted}")
        
        
        return {
            "status": "success", 
            "rows_aggregated": rows_inserted
         
        }

    except Exception as e:
        print(f"❌ Ошибка при группировке данных отчёта: {str(e)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка при группировке данных отчёта: {str(e)}")
        return {"status": "error", "message": str(e)}


@celery_app.task(name="find_lost_track")
def find_lost_track():
    """
    Задача для поиска треков из staging_report_agg, которые не найдены в таблице track.
    Экспортирует результат в Excel файл lost_tracks.xlsx.
    """
    try:
        query = """
        SELECT s.*
        FROM staging_report_agg s
        LEFT JOIN track t ON t.isrc = s.isrc
        WHERE t.id IS NULL;
        """

        query = """ select  track_name, artist_name, authors, isrc, label_own_code, payout_amount  from staging_report_agg  where isFound = false order by payout_amount desc;
        """

        with engine.connect() as conn:
            df = pl.read_database(
                query=query,
                connection=conn,
                infer_schema_length=None
            )

        print(f"🔍 Найдено потерянных треков: {len(df)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"🔍 Найдено потерянных треков: {len(df)}")

        storage_dir = "/app/storage"
        os.makedirs(storage_dir, exist_ok=True)
        output_path = os.path.join(storage_dir, "lost_tracks.xlsx")
        df.write_excel(output_path)

        print(f"✅ Данные экспортированы в файл: {output_path}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Данные экспортированы в файл: {output_path}")

        return {
            "status": "success",
            "lost_tracks_count": len(df),
            "output_file": output_path
        }

    except Exception as e:
        print(f"❌ Ошибка при поиске потерянных треков: {str(e)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка при поиске потерянных треков: {str(e)}")
        return {"status": "error", "message": str(e)}


# ── Транслитерация кириллицы → латиница ─────────────────────────
_TRANSLIT_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "yo", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
    # Казахские буквы
    "ә": "a", "ғ": "g", "қ": "q", "ң": "n",
    "ө": "o", "ұ": "u", "ү": "u", "һ": "h", "і": "i",
}

import re as _re

def _translit(text: str) -> str:
    """Транслитерация кириллицы → латиница, остальные символы без изменений."""
    result = []
    for ch in text:
        low = ch.lower()
        if low in _TRANSLIT_MAP:
            result.append(_TRANSLIT_MAP[low])
        else:
            result.append(low)
    return "".join(result)


def _normalize_name(full_name: str):
    """
    Возвращает (tokens, norm_key_full) для одного full_name.
    1. Транслит → латиница
    2. Удаление спецсимволов (оставляем только буквы, цифры, пробелы)
    3. Lower + split → tokens
    4. Сортировка + склейка через '|' → norm_key_full
    """
    transliterated = _translit(full_name)
    cleaned = _re.sub(r"[^a-z0-9\s]", " ", transliterated)
    tokens = cleaned.split()
    tokens = [t for t in tokens if t]  # убираем пустые



    if not tokens:
        return [], ""

    anchor_tokens = [t for t in tokens if len(t) > 1]    
    initials = sorted([t for t in tokens if len(t) == 1])
    

    norm_key_full = "|".join(sorted(anchor_tokens)) + "||" + "|".join(initials)
    

    return anchor_tokens, norm_key_full


def _normalize_title(full_name: str):
    """
    Возвращает (tokens, norm_key_full) для названия трека.
    1. Транслит → латиница
    2. Токены: (нижний регистр, только буквы/цифры)
    3. Norm Key: snake_case (через подчеркивание)
    """
    if not full_name:
        return [], ""

    # 1. Транслитерация
    transliterated = _translit(full_name).lower()

    # 2. Формируем токены
    # Используем \w+ чтобы сразу получить слова без спецсимволов
    tokens = _re.findall(r'[a-z0-9]+', transliterated)
    
    # 3. Формируем norm_key (snake_case)
    # Заменяем любую последовательность не-букв и не-цифр на одно подчеркивание
    norm_key = _re.sub(r'[^a-z0-9]+', '_', transliterated).strip('_')

    if not tokens:
        return [], ""

    return tokens, norm_key


@celery_app.task(name="normalize_data")
def normalize_data(table_name: str = "person", column_name: str = "full_name", connection=None):
    """
    Заполняет поля {column_name}_tokens и {column_name}_norm_key в таблице {table_name}
    на основе {column_name} (транслит → токены → отсортированный ключ).
    """
    try:
        # Валидация имён таблицы и колонки (только буквы, цифры, подчёркивания)
        import re as _re_val
        if not _re_val.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            return {"status": "error", "message": f"Invalid table_name: {table_name}"}
        if not _re_val.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column_name):
            return {"status": "error", "message": f"Invalid column_name: {column_name}"}

        tokens_col = f"{column_name}_tokens"
        norm_key_col = f"{column_name}_norm_key"

        chunk_size = 50000
        total_updated = 0
        last_id = 0

        update_sql = text(f"""
            UPDATE {table_name}
            SET {tokens_col} = :tokens,
                {norm_key_col} = :norm_key_full
            WHERE id = :pid
        """)

        select_sql = text(
            f"SELECT id, {column_name} FROM {table_name} "
            f"WHERE {column_name} IS NOT NULL and {norm_key_col} is NULL AND id > :last_id "
            f"ORDER BY id LIMIT :chunk_size;"
        )
        print(f"📦 выбираем {select_sql} ")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"📦 выбираем {select_sql} ")

        while True:
            # use provided connection if exists, otherwise open a new one
            if connection:
                conn = connection
                own_conn = False
            else:
                conn = engine.connect()
                own_conn = True

            try:
                rows = conn.execute(select_sql, {"last_id": last_id, "chunk_size": chunk_size}).fetchall()
            finally:
                if own_conn:
                    conn.close()

            if not rows:
                break

            updates = []
            for row in rows:
                row_id = row.id
                value = getattr(row, column_name)
                tokens, norm_key_full = _normalize_title(value)
                updates.append({
                    "pid": row_id,
                    "tokens": tokens,
                    "norm_key_full": norm_key_full,
                })

            if connection:
                # caller manages transaction/commit
                connection.execute(update_sql, updates)
            else:
                with engine.begin() as conn2:
                    conn2.execute(update_sql, updates)

            last_id = rows[-1].id
            total_updated += len(updates)
            print(f"📦 Обновлено {total_updated} (last_id={last_id})")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"📦 Обновлено {total_updated} (last_id={last_id})")

        print(f"✅ Нормализация {table_name}.{column_name} завершена. Обновлено записей: {total_updated}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Нормализация {table_name}.{column_name} завершена. Обновлено записей: {total_updated}")
        return {"status": "success", "total_updated": total_updated}

    except Exception as e:
        print(f"❌ Ошибка при нормализации {table_name}.{column_name}: {str(e)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка при нормализации {table_name}.{column_name}: {str(e)}")
        return {"status": "error", "message": str(e)}


def _split_names(raw: str) -> list[str]:
    """Разделение строки с несколькими именами (аналог clean_and_split из SQL)."""
    parts = _re.split(r"[/,:;]+", raw)
    return [p.strip() for p in parts if p.strip()]


@celery_app.task(name="normalize_staging_report_agg")
def normalize_staging_report_agg(upload_id: str | None = None):
    """
    Заполняет нормализованные поля в staging_report_agg:
    artist_name_tokens, artist_name_norm_key_full,
    authors_tokens, authors_norm_key_full.
    Для каждого поля: split на отдельные имена → _normalize_name → массив norm_key.
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, artist_name, authors, track_name FROM staging_report_agg where isfound = false and upload_id = :upload_id"
            ), {"upload_id": upload_id}).fetchall()

        print(f"📋 staging_report_agg: строк для нормализации: {len(rows)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"📋 staging_report_agg: строк для нормализации: {len(rows)}")

        updates = []
        for row in rows:
            row_id = row.id

            # artist_name
            an_tokens = []
            an_keys = []
            if row.artist_name:
                for name in _split_names(row.artist_name):
                    tokens, norm_key = _normalize_name(name)
                    an_tokens.extend(tokens)
                    an_keys.append(norm_key)
            an_norm_key_full = "|".join(sorted(an_keys)) if an_keys else None

            # authors
            au_tokens = []
            au_keys = []
            if row.authors:
                for name in _split_names(row.authors):
                    tokens, norm_key = _normalize_name(name)
                    au_tokens.extend(tokens)
                    au_keys.append(norm_key)
            au_norm_key_full = "|".join(sorted(au_keys)) if au_keys else None

            # track_name
            _, tn_norm_key = _normalize_title(row.track_name) if row.track_name else ([], "")
            tn_norm_key = tn_norm_key or None

            updates.append({
                "rid": row_id,
                "an_tokens": an_tokens or None,
                "an_norm_key_full": an_norm_key_full,
                "au_tokens": au_tokens or None,
                "au_norm_key_full": au_norm_key_full,
                "tn_norm_key": tn_norm_key,
            })

        batch_size = 5000
        total_updated = 0

        update_sql = text("""
            UPDATE staging_report_agg
            SET artist_name_tokens    = :an_tokens,
                artist_name_norm_key_full = :an_norm_key_full,
                authors_tokens        = :au_tokens,
                authors_norm_key_full = :au_norm_key_full,
                track_name_norm_key   = :tn_norm_key
            WHERE id = :rid
        """)

        for i in range(0, len(updates), batch_size):
            batch = updates[i : i + batch_size]
            with engine.begin() as conn:
                conn.execute(update_sql, batch)
            total_updated += len(batch)
            print(f"📦 Обновлено {total_updated} / {len(updates)}")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"📦 Обновлено {total_updated} / {len(updates)}")

        print(f"✅ Нормализация staging_report_agg завершена. Обновлено: {total_updated}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Нормализация staging_report_agg завершена. Обновлено: {total_updated}")
        return {"status": "success", "total_updated": total_updated}

    except Exception as e:
        print(f"❌ Ошибка при нормализации staging_report_agg: {str(e)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка при нормализации staging_report_agg: {str(e)}")
        return {"status": "error", "message": str(e)}


def _match_by_normalized_name(match_type, partner_id, right_category_id, right_usage_type_id, month, year, match_type_track_name="=", match_type_person="=", upload_id: str | None = None):
    """
    Поиск и вставка в report по track_name + нормализованным данным person.
    Аналог _match_by_name, но сравнение через norm_key_full.
    """
    if match_type == RightCategory.AUTHOR:
        staging_norm_key_col = "authors_norm_key_full"
        roles = "('authors', 'composer', 'lyricist')"
        finding_source = FindingSource.NAME_AUTHOR_NORM
        label = f"NAME+AUTHOR_NORMIZED + NAME:"
        tokens_col = "authors_tokens"
    else:
        staging_norm_key_col = "artist_name_norm_key_full"
        roles = "('artist_name')"
        finding_source = FindingSource.NAME_ARTIST_NORM
        label = f"NAME+ARTIST_NORMIZED + NAME"
        tokens_col = "artist_name_tokens"

    if match_type_track_name == "=":    
        comparison_title = " t.title_norm_key = s.track_name_norm_key"
    
    elif match_type_track_name == "like":
        comparison_title = " t.title_norm_key % s.track_name_norm_key "
        finding_source = (FindingSource.NAME_AUTHOR_NORM_PARTLY 
                        if match_type == RightCategory.AUTHOR 
                        else FindingSource.NAME_ARTIST_NORM_PARTLY)
    else:   
        comparison_title = " lower(trim(split_part(t.title, ' (', 1))) = lower(trim(split_part(s.track_name, ' (', 1)))"
        finding_source = (FindingSource.NAME_AUTHOR_NORM_PARTLY 
                            if match_type == RightCategory.AUTHOR 
                            else FindingSource.NAME_ARTIST_NORM_PARTLY)

    if match_type_person == "=":
        comparison_person =  f"  p.norm_key_full = s.{staging_norm_key_col}"
    else :    
        comparison_person = f"   p.tokens && s.{tokens_col}"

    label += f"TRACK:{match_type_track_name} + PERSON:{match_type_person}"

    insert_sql = text(f"""
    
        WITH matched AS (
            INSERT INTO staging_report_ids (staging_id, track_id, finding_source, upload_id)
            SELECT DISTINCT s.id, t.id, :finding_source, :upload_id
            FROM staging_report_agg s
            JOIN person p ON {comparison_person}
            JOIN track_contribution tc ON tc.person_id = p.id AND tc.role IN {roles}
            JOIN track t ON t.id = tc.track_id
            WHERE s.{staging_norm_key_col} IS NOT NULL 
            AND s.isfound = FALSE and s.upload_id = :upload_id
         
            AND {comparison_title}
            RETURNING staging_id
        )
        UPDATE staging_report_agg SET isfound = TRUE
        WHERE id IN (SELECT staging_id FROM matched) and upload_id = :upload_id;
    """)

    params = {
        "finding_source": finding_source,
        "upload_id": upload_id
    }



    with engine.begin() as connection:
        result = connection.execute(insert_sql, params)
        inserted = result.rowcount
    print(f"✅ Данные добавлены в staging_report_ids по {label}. Записей: {inserted}")



    TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Данные добавлены в staging_report_ids по {label}. Записей: {inserted}")
    return inserted, inserted

@celery_app.task(name="normalize_person_data")
def normalize_person_data(table_name="person", column_name="full_name",
                        tokens_col="tokens", norm_key_col="norm_key_full", connection=None):
    """
    Заполняет поля tokens и norm_key в указанной таблице
    на основе column_name (транслит → токены → отсортированный ключ).
    """
    try:
        import re as _re_val
        if not _re_val.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            return {"status": "error", "message": f"Invalid table_name: {table_name}"}
        if not _re_val.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column_name):
            return {"status": "error", "message": f"Invalid column_name: {column_name}"}
        if not _re_val.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', tokens_col):
            return {"status": "error", "message": f"Invalid tokens_col: {tokens_col}"}
        if not _re_val.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', norm_key_col):
            return {"status": "error", "message": f"Invalid norm_key_col: {norm_key_col}"}

        chunk_size = 50000
        total_updated = 0
        last_id = 0

        select_sql = text(
            f"SELECT id, {column_name} FROM {table_name} "
            f"WHERE {column_name} IS NOT NULL AND {norm_key_col} IS NULL AND id > :last_id "
            f"ORDER BY id LIMIT :chunk_size"
        )

        update_sql = text(f"""
            UPDATE {table_name}
            SET {tokens_col} = :tokens,
                {norm_key_col} = :norm_key_full
            WHERE id = :pid
        """)

        while True:
            # use provided connection if exists, otherwise open a new one
            if connection:
                conn = connection
                own_conn = False
            else:
                conn = engine.connect()
                own_conn = True

            try:
                rows = conn.execute(select_sql, {"last_id": last_id, "chunk_size": chunk_size}).fetchall()
            finally:
                if own_conn:
                    conn.close()

            if not rows:
                break

            updates = []
            for row in rows:
                row_id = row.id
                value = getattr(row, column_name)
                tokens, norm_key_full = _normalize_name(value)
                updates.append({
                    "pid": row_id,
                    "tokens": tokens,
                    "norm_key_full": norm_key_full,
                })

            # perform update inside a transaction if caller did not provide connection
            if connection:
                connection.execute(update_sql, updates)
            else:
                with engine.begin() as conn2:
                    conn2.execute(update_sql, updates)

            last_id = rows[-1].id
            total_updated += len(updates)
            print(f"📦 Обновлено {total_updated} (last_id={last_id})")
            TaskProgress.emit(getattr(current_task.request, 'id', None), f"📦 Обновлено {total_updated} (last_id={last_id})")

        print(f"✅ Нормализация {table_name}.{column_name} завершена. Обновлено записей: {total_updated}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Нормализация {table_name}.{column_name} завершена. Обновлено записей: {total_updated}")
        return {"status": "success", "total_updated": total_updated}

    except Exception as e:
        print(f"❌ Ошибка при нормализации {table_name}.{column_name}: {str(e)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка при нормализации {table_name}.{column_name}: {str(e)}")
        return {"status": "error", "message": str(e)}


def _cleanup_staging_report_tables(conn, upload_id):
    """Очистка staging report tables после синхронизации"""
    t0 = time.time()
    conn.execute(
        text(f"DELETE FROM staging_report WHERE upload_id = :uid"),
        {"uid": upload_id}
    )
  
    elapsed = time.time() - t0
    print(f"🧹 Стейджинг report очищен для сессии {upload_id} ({elapsed:.1f} сек)")
    TaskProgress.emit(getattr(current_task.request, 'id', None), f"🧹 Стейджинг report очищен для сессии {upload_id} ({elapsed:.1f} сек)")


def calculate_report_data(task_id: str, year: int, month_from: int, month_to: int, right_category_id: int, right_usage_type_id: int, label_ids: Optional[List[int]] = None):
    """
    Расчет данных отчета на основе параметров.
    Пока просто выводит параметры.
    """
    print(f"📊 Начало расчета отчета")
    print(f"  - Год: {year}")
    print(f"  - Период месяцев: {month_from} - {month_to}")
    print(f"  - Категория прав: {right_category_id}")
    print(f"  - Тип использования: {right_usage_type_id}")
    print(f"  - Лейблы: {label_ids if label_ids else 'все'}")
    
    TaskProgress.emit(task_id, f"📊 Начало расчета отчета для периода {month_from}-{month_to}/{year}")
    TaskProgress.emit(task_id, f"  Категория прав: {right_category_id}, Тип использования: {right_usage_type_id}")
    
    if label_ids:
        TaskProgress.emit(task_id, f"  Фильтр по лейблам: {label_ids}")
    else:
        TaskProgress.emit(task_id, "  Лейблы: все")
    
    print(f"✅ Расчет данных отчета завершен")
    TaskProgress.emit(task_id, "✅ Расчет данных отчета завершен")


def export_report_data_in_file(task_id: str, year: int, month_from: int, month_to: int, right_category_id: int, right_usage_type_id: int, label_ids: Optional[List[int]] = None):
    """
    Экспорт данных отчета в файл.
    Пока просто выводит параметры.
    """
    print(f"💾 Начало экспорта отчета в файл")
    print(f"  - Год: {year}")
    print(f"  - Период месяцев: {month_from} - {month_to}")
    print(f"  - Категория прав: {right_category_id}")
    print(f"  - Тип использования: {right_usage_type_id}")
    print(f"  - Лейблы: {label_ids if label_ids else 'все'}")
    
    TaskProgress.emit(task_id, f"💾 Начало экспорта отчета для периода {month_from}-{month_to}/{year}")
    
    filename = f"report_{year}_{month_from}_{month_to}_{right_category_id}_{right_usage_type_id}.xlsx"
    print(f"  - Файл: {filename}")
    TaskProgress.emit(task_id, f"  Файл: {filename}")
    
    print(f"✅ Экспорт отчета в файл завершен")
    TaskProgress.emit(task_id, "✅ Экспорт отчета в файл завершен")


@celery_app.task(name="create_report_task")
def create_report_task(year: int, month_from: int, month_to: int, right_category_id: int, right_usage_type_id: int, label_ids: Optional[str] = None):
    """
    Создание отчета:
    1. Расчет данных отчета (calculate_report_data)
    2. Экспорт данных в файл (export_report_data_in_file)
    """
    try:
        task_id = current_task.request.id
        print(f"🚀 Задача создания отчета запущена (task_id: {task_id})")
        TaskProgress.emit(task_id, f"🚀 Задача создания отчета запущена")
        
        # Преобразование label_ids из строки в список
        labels_list = None
        if label_ids:
            if isinstance(label_ids, str) and label_ids.strip():
                try:
                    labels_list = [int(lid.strip()) for lid in label_ids.split(",") if lid.strip()]
                except ValueError:
                    pass
            elif isinstance(label_ids, list):
                labels_list = label_ids
        
        # Этап 1: Расчет данных
        print(f"⏳ Этап 1: Расчет данных отчета")
        TaskProgress.emit(task_id, "⏳ Этап 1: Расчет данных отчета")
        calculate_report_data(task_id, year, month_from, month_to, right_category_id, right_usage_type_id, labels_list)
        
        # Этап 2: Экспорт в файл
        print(f"⏳ Этап 2: Экспорт данных в файл")
        TaskProgress.emit(task_id, "⏳ Этап 2: Экспорт данных в файл")
        export_report_to_excel_total(task_id, year, month_from, month_to, right_category_id, right_usage_type_id, labels_list)
        
        print(f"✅ Задача создания отчета завершена успешно")
        TaskProgress.emit(task_id, "✅ Задача создания отчета завершена успешно")
        
        return {
            "status": "success",
            "task_id": task_id,
            "params": {
                "year": year,
                "month_from": month_from,
                "month_to": month_to,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "label_ids": labels_list
            }
        }
    except Exception as e:
        print(f"❌ Ошибка при создании отчета: {str(e)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка при создании отчета: {str(e)}")
        return {"status": "error", "message": str(e)}




def add_rights_to_report(df_base: pl.DataFrame, df_rights: pl.DataFrame, df_ext: pl.DataFrame, id_col: str) -> pl.DataFrame:
    # 1. FIX: Принудительно приводим ID к одному типу и материализуем данные
    df_base = df_base.with_columns(pl.col(id_col).cast(pl.Int64)).rechunk()
    
    if not df_rights.is_empty():
        df_rights = df_rights.with_columns(pl.col(id_col).cast(pl.Int64))
    if not df_ext.is_empty():
        df_ext = df_ext.with_columns(pl.col(id_col).cast(pl.Int64))

    # --- Объединение прав ---
    if len(df_ext) > 0:
        if len(df_rights) > 0:
            existing_rights = df_rights.select([id_col, "category", "right_usage_type_code"]).unique()
            df_ext_filtered = df_ext.join(
                existing_rights,
                on=[id_col, "category", "right_usage_type_code"],
                how="anti"
            )
        else:
            df_ext_filtered = df_ext

        df_rights_all = pl.concat([df_rights, df_ext_filtered], how="vertical")
        df_rights_all = df_rights_all.unique(
            subset=[id_col, "category", "right_holder_name", "right_usage_type_code"]
        )
    else:
        df_rights_all = df_rights

    if df_rights_all.is_empty():
        return df_base

    # 2. FIX: Генерируем RN через cum_count (это ты уже сделала, оставляем)
    df_rights_all = df_rights_all.with_columns(
        rn = pl.lit(1).cum_count().over([id_col, "category", "right_usage_type_code"])
    ).rechunk()

    category_map = {"Author": "авторские", "Related": "смежные"}
    groups = df_rights_all.select(["category", "right_usage_type_code"]).unique().sort(["category", "right_usage_type_code"])

    for row in groups.iter_rows(named=True):
        cat = row["category"]
        rut_code = row["right_usage_type_code"]
        cat_label = category_map.get(cat, cat)

        df_group = df_rights_all.filter(
            (pl.col("category") == cat) & (pl.col("right_usage_type_code") == rut_code)
        )
        
        # 3. FIX: Безопасное получение макс. значения без использования .item()
        max_rn_val = df_group["rn"].max()
        max_rn = int(max_rn_val) if max_rn_val is not None else 0

        for i in range(1, max_rn + 1):
            suffix = f" {i}" if max_rn > 1 else ""

            # Формируем группу для джойна
            group_i = df_group.filter(pl.col("rn") == i).select([
                pl.col(id_col),
                pl.col("share_percentage").alias(f"Доля {cat_label} прав {rut_code}{suffix}, %"),
                pl.col("right_holder_name").alias(f"Правообладатель ({cat_label}) {rut_code}{suffix}"),
            ])
            
            # Джойним
            df_base = df_base.join(group_i, on=id_col, how="left")
            
    return df_base

    
@celery_app.task(name="export_report_to_excel_total")
def export_report_to_excel_total(
    task_id: int,
    year: int,
    month_from: int,
    month_to: int,
    right_category_id: int,
    right_usage_type_id: int,
    labels: Optional[List[int]] = None
):
    
    if right_category_id == RightCategory.BOTH:
        category_filter = f"IN ({RightCategory.AUTHOR}, {RightCategory.RELATED})"
    else:
        category_filter = f"= {right_category_id}"
    try:
        print("📤 Начинаем экспорт сводного отчёта в Excel (по правообладателям)...")
        TaskProgress.emit(getattr(current_task.request, 'id', None), "📤 Начинаем экспорт...")


        total_source_money = 0.0
        total_distributed_money = 0.0

        # ---------- 1. Построение основного запроса (с track_id и right_holder_name) ----------
        labels_condition = ""
        labels_params = {}
        if labels:
            placeholders = ",".join([f":lid{i}" for i in range(len(labels))])
            labels_condition = f" AND  tl.label_id IN ({placeholders}) "
            for i, lid in enumerate(labels):
                labels_params[f"lid{i}"] = lid

        base_query = text(f"""
            SELECT
                t.track_id as track_id,
                l.id AS label_id,
                r.r_label_own_code AS "Отчет код лейбла",
                r.r_isrc AS "Отчет ISRC",
                r.r_track_name AS "Отчет название трека",
                r.r_artist_name AS "Отчет исполнитель",
                r.r_authors AS "Отчет авторы",
                t.label_own_code AS "Код лейбла",
                t.isrc AS "Код ISRC",
                t.track_name AS "Название трека",
                t.artist_name AS "Исполнитель",
                t.composer AS "Автор музыки",
                t.lyricist AS "Автор текста",
                t.authors AS "Авторы",
                r.play_count AS "Кол-во прослушиваний",
                r.payout_amount AS "Сумма выплат",
                r.price_per_play AS "Цена за прослушивание",
                fs.code AS "Источник совпадения",
                l.code AS  label_code
            FROM report r
            left JOIN mv_track_extended t ON t.track_id = r.track_id
            left JOIN track_label tl ON tl.track_id = t.track_id
            left JOIN label l ON l.id = tl.label_id
            LEFT JOIN finding_source fs ON fs.id = r.finding_source
            WHERE r.right_category_id = :right_category_id
            AND r.right_usage_type_id = :right_usage_type_id
            AND r.report_year = :year
            AND r.report_month BETWEEN :month_from AND :month_to
            {labels_condition}
            ORDER BY l.code
        """)

        with engine.connect() as conn:
            query_params = {
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "year": year,
                "month_from": month_from,
                "month_to": month_to,
            }
            if labels:
                query_params.update(labels_params)

            result = conn.execute(base_query, query_params)
            
            data = list(result.mappings())
            df_base = pl.DataFrame(data, infer_schema_length=None)

            # Приведение Object -> Utf8 (если нужно)
            if not df_base.is_empty():
                df_base = df_base.with_columns(pl.col(pl.Object).cast(pl.Utf8))
            print("Сбор данных завершён, добавляем права к трекам...")
            TaskProgress.emit(getattr(current_task.request, 'id', None), "Сбор данных завершён, добавляем права к трекам...")



            # Метаданные для имени файла
            meta_row = conn.execute(text(f"""
                SELECT COALESCE(p.code, p.id::TEXT) AS partner_code,
                       rc.name AS right_category_name,
                       rut.code AS right_usage_type_code
                FROM partners p
                CROSS JOIN right_category rc
                CROSS JOIN right_usage_type rut
                WHERE rc.id  {category_filter} AND rut.id = :right_usage_type_id
            """), {
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
            }).fetchone()

            partner_code = meta_row.partner_code if meta_row else "unknown_partner"
            right_category_name = meta_row.right_category_name if meta_row else str(right_category_id)
            right_usage_type_code = meta_row.right_usage_type_code if meta_row else str(right_usage_type_id)

        with engine.connect() as conn:
            track_ids = df_base["track_id"].unique().to_list()
            if track_ids:
                # Прямые права
                rights_query = text(f"""
                    SELECT DISTINCT
                        tr.track_id AS track_id,
                        rc.name AS category,
                        rh.name AS right_holder_name,
                        tr.share_percentage,
                        rut.code AS right_code,
                        rh.label_id as label_id,
                        ROW_NUMBER() OVER(
                        PARTITION BY tr.track_id, rc.name, rut.code 
                        ORDER BY tr.share_percentage DESC
                    ) as rn
                    FROM track_right tr
                    JOIN right_category rc ON rc.id = tr.right_category_id
                    JOIN right_holder rh ON rh.id = tr.right_holder_id
                    JOIN right_usage_type rut ON rut.id = tr.right_usage_type_id
                    WHERE tr.track_id = ANY(:track_ids)
                    AND tr.right_category_id {category_filter}
                     AND tr.right_usage_type_id = :rutid
                """)
                #res_rights = conn.execute(rights_query, {"track_ids": track_ids})
                #df_rights = pl.DataFrame(res_rights.mappings()) 
                df_rights = pl.read_database(rights_query, conn, 
                                        execute_options={"parameters": {
                                            "track_ids": track_ids,
                                            "rcid": right_category_id,
                                            "rutid": right_usage_type_id
                                        }})
               
               
               
               



   



      

        storage_dir = "/app/storage"
        os.makedirs(storage_dir, exist_ok=True)
        filename = f"report_total_{year}_{month_from}_{month_to}_{partner_code}_{right_category_name}_{right_usage_type_code}.xlsx"
        output_path = os.path.join(storage_dir, filename)

        # ---------- 4. Обработка пустого результата ----------
        if df_base.is_empty():
            empty_df = pl.DataFrame({"Сообщение": ["Нет данных для указанных параметров"]})
            empty_df.write_excel(output_path, worksheet="Информация")
            print("⚠️ Нет данных для экспорта, создан файл с сообщением.")
            TaskProgress.emit(getattr(current_task.request, 'id', None), "⚠️ Нет данных для экспорта.")
            return {
                "status": "success",
                "rows_exported": 0,
                "sheets_count": 0,
                "output_file": output_path,
            }

        # ---------- 5. Разбивка на листы и запись в Excel ----------
        holders_mapping = (
                df_base.select(["label_code", "label_id"])
                .unique()
                .drop_nulls()
                .to_dicts()
            )

        if not df_rights.is_empty():
         
            df_rights = df_rights.with_columns([
                (
                    pl.col("category") + pl.lit(" ") + 
                    pl.col("right_code") + pl.lit(" ") + 
                    pl.col("rn").cast(pl.Utf8)
                ).alias("base_name")
            ])

        with xlsxwriter.Workbook(output_path) as workbook:
            # --- 5.1 Сводный лист ---
            df_summary = (
                df_base.group_by("label_code")
                .agg([
                    pl.col("Кол-во прослушиваний").sum(),
                    pl.col("Сумма выплат").sum()
                ])
                .sort("label_code")
                .rename({"label_code": "Правообладатель"})
            )
            df_summary.write_excel(workbook, worksheet="Все данные")

            # --- 5.2 Детальные листы по лейблам ---
            total_source_money = float(df_base["Сумма выплат"].sum())
            
            for holder in holders_mapping:
                h_code = str(holder["label_code"])
                h_id = holder["label_id"]

                # Фильтруем данные и права для конкретного лейбла
                df_holder_base = df_base.filter(pl.col("label_id") == h_id)
                df_rights_local = df_rights.filter(pl.col("label_id") == h_id)

                # Задаем пустые списки-заглушки заранее
                rights_columns = []
                payout_columns = []

                if not df_rights_local.is_empty():
                    # 1. Создаем уникальный ключ для колонки: "Категория + Тип + Имя"
                    # Это гарантирует, что "Author PUB Эффектив" всегда будет одной колонкой
                    df_rights_local = df_rights_local.with_columns([
                        (
                            pl.col("category") + pl.lit(" ") + 
                            pl.col("right_code") + pl.lit(" ") + 
                            pl.col("right_holder_name")
                        ).alias("column_key")
                    ])

                    # 2. Пивот для имен (записываем само имя правообладателя)
                    df_h_pivot = df_rights_local.pivot(
                        values="right_holder_name",
                        index="track_id", 
                        on="column_key",
                        aggregate_function="first"
                    )
                    
                    # 3. Пивот для процентов
                    # К ключу добавляем " %", чтобы колонки процентов шли следом
                    df_s_pivot = df_rights_local.with_columns(
                        (pl.col("column_key") + pl.lit(" %")).alias("share_column_key")
                    ).pivot(
                        values="share_percentage",
                        index="track_id",
                        on="share_column_key",
                        aggregate_function="first"
                    )

                    # 4. Соединяем всё в один лист
                    df_final_sheet = df_holder_base.join(df_h_pivot, on="track_id", how="left")
                    df_final_sheet = df_final_sheet.join(df_s_pivot, on="track_id", how="left")

                    # Список колонок, которые образовались после пивота (перенесли сюда для безопасности)
                    rights_columns = [c for c in df_h_pivot.columns if c != "track_id"] + \
                                    [c for c in df_s_pivot.columns if c != "track_id"]
                else:
                    df_final_sheet = df_holder_base

                # Убираем технические колонки
                #df_to_save = df_final_sheet.drop(["label_code", "track_id", "label_id"])

                # ---------- АГРЕГАЦИЯ ПРОИЗВЕДЕНИЯ (СХЛОПЫВАНИЕ СУФФИКСОВ) ----------
                # 1. Выделяем базовый код без суффикса (из колонки "Код лейбла")
                df_final_sheet = df_final_sheet.with_columns(
                    pl.col("Код лейбла").str.split("-").list.get(0).alias("clean_label_code")
                )

                # ---------- РАСЧЕТ СУММЫ К РАСПРЕДЕЛЕНИЮ ----------
                share_cols = [c for c in df_final_sheet.columns if c.endswith(" %")]
                
                if share_cols:
                    coef = 0.5 if right_category_id == RightCategory.BOTH else 1.0
                    for s_col in share_cols:
                        payout_col_name = s_col.replace(" %", " Сумма к распределению")
                        payout_columns.append(payout_col_name)
                        
                        df_final_sheet = df_final_sheet.with_columns(
                            (
                                pl.col("Сумма выплат") * coef * (pl.col(s_col).fill_null(0.0) / 100.0)
                            ).alias(payout_col_name)
                        )

                # 2. Группируем по clean_label_code, суммируем деньги, схлопываем права через max()
                df_to_save = (
                    df_final_sheet.group_by("clean_label_code")
                    .agg([
                        pl.col("Отчет код лейбла").first(),
                        pl.col("Отчет ISRC").first(),
                        pl.col("Отчет название трека").first(),
                        pl.col("Отчет исполнитель").first(),
                        pl.col("Отчет авторы").first(),
                        pl.col("Код ISRC").fill_null("").max(),
                        pl.col("Название трека").first(),
                        pl.col("Исполнитель").first(),
                        pl.col("Автор музыки").first(),
                        pl.col("Автор текста").first(),
                        pl.col("Авторы").first(),
                        pl.col("Источник совпадения").first(),
                        pl.col("Цена за прослушивание").mean(),
                        
                        # Суммируем статистику прослушиваний и денег со всех суффиксов
                        pl.col("Кол-во прослушиваний").sum(),
                        pl.col("Сумма выплат").sum(),
                        
                        # Собираем права со всех суффиксов в одну строку (игнорируя null)
                        *[pl.col(c).max() for c in rights_columns],

                        # Добавляем суммы к распределению (схлопываем через сумму)
                        *[pl.col(c).sum() for c in payout_columns]
                    ])
                    .rename({"clean_label_code": "Код лейбла"})
                )
                # --------------------------------------------------------------------

                if payout_columns and not df_to_save.is_empty():
                    sheet_sum = df_to_save.select(pl.sum_horizontal(payout_columns)).sum().item()
                    if sheet_sum is not None:
                        total_distributed_money += sheet_sum

                # Генерируем безопасное имя листа (не более 31 символа)
                sheet_name = re.sub(r'[\\/*?:\[\]]', '_', h_code)[:31]
                
                # Проверка на уникальность имени листа
                original_name = sheet_name
                counter = 1
                while workbook.get_worksheet_by_name(sheet_name) is not None:
                    suffix = f"_{counter}"
                    sheet_name = original_name[:31 - len(suffix)] + suffix
                    counter += 1

                # ЗАПИСЬ
                df_to_save.write_excel(workbook, worksheet=sheet_name)
                
                print(f"📄 Вкладка создана для: {h_code}")
                TaskProgress.emit(getattr(current_task.request, 'id', None), f"  📄 Вкладка создана для: {holder}")


        unassigned_money = total_source_money - total_distributed_money
        balance_report = (
            f"\n========================================\n"
            f"📊 ФИНАНСОВАЯ СВЕРКА БАЛАНСА ОТЧЕТА:\n"
            f"💰 Исходная сумма выплат (Всего): {total_source_money:,.2f}\n"
            f"✅ Успешно распределено по долям: {total_distributed_money:,.2f}\n"
            f"⚠️ Остаток (невостребованная сумма): {unassigned_money:,.2f}\n"
            f"========================================\n"
        )
        print(balance_report)
        TaskProgress.emit(getattr(current_task.request, 'id', None), balance_report)
        
        print(f"✅ Сводный отчёт экспортирован в файл: {output_path}")
        print(f"📊 Всего записей: {len(df_base)}, вкладок: {len(holders_mapping) + 1}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Файл: {output_path}")
        return {
            "status": "success",
            "rows_exported": len(df_base),
            "sheets_count": len(holders_mapping) + 1,
            "output_file": output_path,
        }

    except Exception as e:
        print(f"❌ Ошибка при экспорте сводного отчёта в Excel: {str(e)}")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"❌ Ошибка: {str(e)}")
        return {"status": "error", "message": str(e)}





@celery_app.task(name="calculate_and_save_distribution_sql")
def calculate_and_save_distribution_sql(
    task_id: int,
    year: int,
    month_from: int,
    month_to: int,
    right_category_id: int,
    right_usage_type_id: int,
    labels: Optional[List[int]] = None
):
    category_filter = (
        f"IN ({RightCategory.AUTHOR}, {RightCategory.RELATED})"
        if right_category_id == RightCategory.BOTH
        else f"= {right_category_id}"
    )

    labels_condition = ""
    labels_params = {}
    if labels:
        placeholders = ",".join([f":lid{i}" for i in range(len(labels))])
        labels_condition = f" AND tl.label_id IN ({placeholders}) "
        for i, lid in enumerate(labels):
            labels_params[f"lid{i}"] = lid

    try:
        print("🚀 Запуск прозрачного двухэтапного расчета распределения...")

        with engine.begin() as conn:
            
            # --- ЭТАП 1: ОЧИСТКА СТАРЫХ КЭШЕЙ И РАСЧЕТОВ ---
            conn.execute(text("""
                DELETE FROM report_track_rights_cache 
                WHERE report_year = :year AND month_from = :month_from AND month_to = :month_to
                  AND right_category_id = :right_category_id AND right_usage_type_id = :right_usage_type_id;
            """), {"year": year, "month_from": month_from, "month_to": month_to, "right_category_id": right_category_id, "right_usage_type_id": right_usage_type_id})

            delete_distribution = text("""
                DELETE FROM report_distribution 
                WHERE report_year = :year AND report_month BETWEEN :month_from AND :month_to
                  AND right_category_id = :right_category_id AND right_usage_type_id = :right_usage_type_id;
            """)
            conn.execute(delete_distribution, {"year": year, "month_from": month_from, "month_to": month_to, "right_category_id": right_category_id, "right_usage_type_id": right_usage_type_id})


            # --- ЭТАП 2: ЗАМОРОЗКА РЕЗУЛЬТИРУЮЩИХ ПРАВ В ОТДЕЛЬНУЮ ТАБЛИЦУ ---
          
            cache_rights_query = text(f"""
                INSERT INTO report_track_rights_cache (
                    report_year, month_from, month_to,
                    staging_id, track_id, right_holder_id, right_category_id, right_usage_type_id, share_percentage
                )
                WITH raw_candidates AS (
                    -- Шаг 1: Собираем вообще всех кандидатов из сессии
                    SELECT 
                        ri.staging_id,
                        ri.track_id,
                        ri.finding_source
                    FROM staging_report_ids ri 
                    JOIN report r ON r.upload_id = ri.upload_id
                    WHERE r.right_category_id = :right_category_id
                    AND r.right_usage_type_id = :right_usage_type_id
                    AND r.report_year = :year
                    AND r.report_month BETWEEN :month_from AND :month_to
                    {labels_condition}
                ),
                candidates_with_rights AS (
                    -- Шаг 2: Сразу вытаскиваем права для кандидатов и схлопываем дубли правообладателей по MAX
                    SELECT 
                        c.staging_id,
                        c.track_id,
                        c.finding_source,
                        tr.right_holder_id,
                        tr.right_category_id,
                        tr.right_usage_type_id,
                        MAX(tr.share_percentage) AS max_share_percentage
                    FROM raw_candidates c
                    INNER JOIN track_right tr ON tr.track_id = c.track_id
                    WHERE tr.right_usage_type_id = :right_usage_type_id
                        AND tr.right_category_id {category_filter}
                    GROUP BY c.staging_id, c.track_id, c.finding_source, tr.right_holder_id, tr.right_category_id, tr.right_usage_type_id
                ),
                track_total_shares AS (
                        -- Считаем суммарную долю для каждого трека в рамках одной строки отчета
                        SELECT 
                            staging_id, 
                            track_id, 
                            SUM(max_share_percentage) AS total_share
                        FROM candidates_with_rights
                        GROUP BY staging_id, track_id
                    ),
                    best_track_per_staging AS (
                        -- Ранжирование ИСКЛЮЧИТЕЛЬНО по доле прав (total_share)
                        SELECT staging_id, track_id
                        FROM (
                            SELECT 
                                staging_id,
                                track_id,
                                ROW_NUMBER() OVER (
                                    PARTITION BY staging_id 
                                    ORDER BY total_share DESC, track_id ASC
                                ) AS rn
                            FROM track_total_shares
                        ) t
                        WHERE rn = 1
                    )
                    -- Финальная вставка данных победителя
                    SELECT 
                        :year, :month_from, :month_to,
                        b.staging_id, 
                        cr.track_id, 
                        cr.right_holder_id, 
                        cr.right_category_id, 
                        cr.right_usage_type_id,
                        cr.max_share_percentage
                    FROM best_track_per_staging b
                    JOIN candidates_with_rights cr 
                        ON cr.staging_id = b.staging_id 
                        AND cr.track_id = b.track_id;
               
            """)
            
            query_params = {
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "year": year,
                "month_from": month_from,
                "month_to": month_to,
                "both_category_id": RightCategory.BOTH,
                "author_category_id": RightCategory.AUTHOR
            }
            if labels:
                query_params.update(labels_params)

            conn.execute(cache_rights_query, query_params)


            cache_rights_query_add_author_rights = text(f"""
                INSERT INTO report_track_rights_cache (
                    report_year, month_from, month_to,
                    staging_id, track_id, right_holder_id, right_category_id, right_usage_type_id, share_percentage
                )
                SELECT 
                    c.report_year, c.month_from, c.month_to,
                    c.staging_id,
                    t_main.id,
                    tr.right_holder_id,
                    tr.right_category_id,
                    tr.right_usage_type_id,
                    tr.share_percentage
                FROM report_track_rights_cache c
                JOIN track t_suffix ON t_suffix.id = c.track_id
                JOIN track t_main ON t_main.label_own_code = REGEXP_REPLACE(t_suffix.label_own_code, '-[A-Za-z0-9]+$', '')
                JOIN track_right tr ON tr.track_id = t_main.id
                WHERE c.report_year = :year
                AND c.month_from = :month_from   AND c.month_to = :month_to
                AND tr.right_usage_type_id = :right_usage_type_id
                AND tr.right_category_id = :author_category_id  
                AND t_suffix.label_own_code ~ '-[A-Za-z0-9]+$'
                -- ГЛАВНОЕ ИЗМЕНЕНИЕ: проверяем, нет ли уже этой категории для этого staging_id
                AND NOT EXISTS (
                    SELECT 1 FROM report_track_rights_cache c2 
                    WHERE c2.staging_id = c.staging_id 
                    AND c2.right_category_id = :author_category_id
                );
                            """)
            conn.execute(cache_rights_query_add_author_rights, query_params)


            print("👁️ Права успешно заморожены в таблице `report_track_rights_cache`.")



            # выбрать лучшие права для каждого staging_id 

            query_distributed = text(f"""
                INSERT INTO report_distribution (
                    report_id, track_id, right_holder_id, 
                    report_year, report_month, right_category_id, right_usage_type_id, 
                    source_payout_amount, share_percentage, coef, 
                    distributed_amount, not_distributed_amount
                )
                SELECT
                    r.id AS report_id,
                    rcache.track_id,
                    rcache.right_holder_id,
                    r.report_year,
                    r.report_month,
                    rcache.right_category_id,
                    rcache.right_usage_type_id,
                    ri.payout_amount AS source_payout_amount,
                    rcache.share_percentage,
                    CASE WHEN r.right_category_id = :both_category_id THEN 0.50 ELSE 1.00 END AS coef,

                    (ri.payout_amount * (CASE WHEN r.right_category_id = :both_category_id THEN 0.50 ELSE 1.00 END) * (rcache.share_percentage / 100.0)) AS distributed_amount,
                    0.0000 AS not_distributed_amount
                FROM staging_report_agg ri 
                JOIN report r ON r.upload_id = ri.upload_id
                -- Просто джойнимся к кэшу напрямую по staging_id. Там уже чистота и порядок!
                INNER JOIN report_track_rights_cache rcache ON 
                    rcache.staging_id = ri.id  
                    AND rcache.right_usage_type_id = r.right_usage_type_id    
                    AND rcache.report_year = :year
                    AND rcache.month_from = :month_from
                    AND rcache.month_to = :month_to
                    AND ((r.right_category_id = :both_category_id AND rcache.right_category_id IN (1, 2))
                            OR (r.right_category_id != :both_category_id AND rcache.right_category_id = r.right_category_id))
                WHERE r.right_category_id = :right_category_id
                AND r.right_usage_type_id = :right_usage_type_id
                AND r.report_year = :year
                AND r.report_month BETWEEN :month_from AND :month_to
                {labels_condition};
            """)
            result = conn.execute(query_distributed, query_params)
            rows_inserted = result.rowcount
            print(f"✅ Расчет distributed завершен . Записано строк: {rows_inserted}")
  
           
            print(f"✅ Расчет not_distributed завершен. Записано строк: {rows_inserted}")
                    
        return {"status": "success", "rows_inserted": rows_inserted}

    except Exception as e:
        print(f"❌ Ошибка вычислений: {str(e)}")
        return {"status": "error", "message": str(e)}





@celery_app.task(name="export_report_distribution_to_excel")
def export_report_distribution_to_excel(
        task_id: int,
        year: int,
        month_from: int,
        month_to: int,
        right_category_id: int,
        right_usage_type_id: int,
        labels: Optional[List[int]] = None
    ):
        if right_category_id == RightCategory.BOTH:
            category_filter = f"IN ({RightCategory.AUTHOR}, {RightCategory.RELATED})"
        else:
            category_filter = f"= {right_category_id}"

        try:
            print("📤 Начинаем экспорт сводного отчёта из готовых распределений (report_distribution)...")
            TaskProgress.emit(getattr(current_task.request, 'id', None), "📤 Начинаем экспорт...")

            total_source_money = 0.0
            total_distributed_money = 0.0

            # ---------- 1. Подготовка параметров и условий ----------
            labels_condition_base = ""
            labels_condition_rights = ""
            labels_params = {}
            if labels:
                placeholders = ",".join([f":lid{i}" for i in range(len(labels))])
                labels_condition_base = f" AND l.id IN ({placeholders}) "
                labels_condition_rights = f" AND tl.label_id IN ({placeholders}) "
                for i, lid in enumerate(labels):
                    labels_params[f"lid{i}"] = lid

            query_params = {
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "year": year,
                "month_from": month_from,
                "month_to": month_to,
            }
            if labels:
                query_params.update(labels_params)

            # ---------- 2. Запрос базовых данных (уже привязанных к report_distribution) ----------
            # Используем DISTINCT, чтобы получить 1 строку на 1 report_id, так как 
            # payout_amount дублируется в distribution для разных ПО.
            base_query = text(f"""
                SELECT DISTINCT
                
                ra.id AS staging_id,
                ra.label_own_code AS "Отчет код лейбла",
                ra.isrc AS "Отчет ISRC",
                ra.track_name AS "Отчет название трека",
                ra.artist_name AS "Отчет исполнитель",
                ra.authors AS "Отчет авторы",
           
                
                MAX(t.label_own_code) AS "Код лейбла",
                MAX(t.isrc) AS "Код ISRC",
                MAX(t.track_name) AS "Название трека",
                MAX(t.artist_name) AS "Исполнитель",
                MAX(t.composer) AS "Автор музыки",
                MAX(t.lyricist) AS "Автор текста",
                MAX(t.authors) AS "Авторы",
               
                ra.play_count AS "Кол-во прослушиваний",
                ra.payout_amount AS "Сумма выплат",
                ra.price_per_play AS "Цена за прослушивание"

                FROM staging_report_agg ra
                JOIN report r ON r.upload_id = ra.upload_id
                JOIN report_track_rights_cache rtc ON rtc.staging_id = ra.id
                JOIN mv_track_extended t ON t.track_id = rtc.track_id
                WHERE r.report_year = :year
                AND r.report_month BETWEEN :month_from AND :month_to
                AND r.right_category_id = :right_category_id
                AND r.right_usage_type_id = :right_usage_type_id
                {labels_condition_base}
                GROUP BY ra.id, ra.label_own_code, ra.isrc, ra.track_name, ra.artist_name, ra.authors, ra.play_count, ra.payout_amount, ra.price_per_play
            
            """)

            with engine.connect() as conn:
                result = conn.execute(base_query, query_params)
                df_base = pl.DataFrame(list(result.mappings()), infer_schema_length=None)

                if not df_base.is_empty():
                    df_base = df_base.with_columns(pl.col(pl.Object).cast(pl.Utf8))
                if df_base.is_empty():
                    return {"status": "success", "rows_exported": 0} 
                print("Сбор базы завершён, собираем распределённые права...")
                TaskProgress.emit(getattr(current_task.request, 'id', None), "Сбор базы завершён, загружаем права...")



                staging_ids = df_base["staging_id"].to_list()
                query_params["staging_ids"] = staging_ids
                
                rights_query = text(f"""
                    SELECT 
                        rtc.staging_id, rc.name AS category, rh.name AS right_holder_name,
                        rtc.share_percentage, rut.code AS right_code, rh.label_id, l.code AS label_code,
                        ROW_NUMBER() OVER(PARTITION BY rtc.staging_id, rc.name, rut.code ORDER BY rtc.share_percentage DESC) as rn
                    FROM report_track_rights_cache rtc
                    JOIN right_category rc ON rc.id = rtc.right_category_id
                    JOIN right_holder rh ON rh.id = rtc.right_holder_id
                    JOIN right_usage_type rut ON rut.id = rtc.right_usage_type_id
                    JOIN label l ON l.id = rh.label_id
                    WHERE rtc.staging_id = ANY(:staging_ids)
                    {labels_condition_base}
                """)
                df_rights = pl.read_database(rights_query, conn, execute_options={"parameters": query_params})


                unclaimed_query = text(f"""
                    SELECT 
                        ra.id AS staging_id,
                        ra.label_own_code AS "Отчет код лейбла",
                        ra.isrc AS "Отчет ISRC",
                        ra.track_name AS "Отчет название трека",
                        ra.artist_name AS "Отчет исполнитель",
                        ra.authors AS "Отчет авторы",
                        ra.play_count AS "Кол-во прослушиваний",
                        ra.payout_amount AS "Сумма выплат"
                    FROM staging_report_agg ra
                    JOIN report r ON r.upload_id = ra.upload_id
                    WHERE r.report_year = :year
                    AND r.report_month BETWEEN :month_from AND :month_to
                    AND r.right_category_id = :right_category_id
                    AND r.right_usage_type_id = :right_usage_type_id
                    AND ra.id NOT IN (SELECT staging_id FROM report_track_rights_cache)
             
                """)
                df_unclaimed = pl.read_database(unclaimed_query, conn, execute_options={"parameters": query_params})



                # 4. Подготовка файла
                storage_dir = "/app/storage"
                os.makedirs(storage_dir, exist_ok=True)
                filename = f"report_{year}_{month_from}_{month_to}.xlsx"
                output_path = os.path.join(storage_dir, filename)

                # 5. Генерация вкладок по лейблам
                all_label_ids = df_rights["label_id"].unique().to_list()
                
                all_summaries = []

                with xlsxwriter.Workbook(output_path) as workbook:
                    # 1. Цикл по лейблам
                    for l_id in all_label_ids:
                        df_r_local = df_rights.filter(pl.col("label_id") == l_id)
                        label_code = df_r_local["label_code"][0]
                        
                        # Формируем структуру прав (1 staging_id = 1 строка с колонками %)
                        df_r_local = df_r_local.with_columns(
                            (pl.col("category") + " " + pl.col("right_code") + " %").alias("s_key")
                        )

                        # 2. ПРАВИЛЬНЫЙ ПИВОТ:
                        # Мы не группируем заранее, а позволяем методу pivot сделать всё за один шаг.
                        # aggregate_function="sum" внутри pivot сам схлопнет дубли по staging_id,
                        # если они там есть.
                        s_pivot = df_r_local.pivot(
                            values="share_percentage", 
                            index="staging_id", 
                            on="s_key", 
                            aggregate_function="sum"
                        )
                                                                        
                        # Джойним к базе (INNER JOIN оставляет только распределенные)
                        df_sheet = df_base.join(s_pivot, on="staging_id", how="inner")
                        
                        # Считаем суммы (умножаем на деньги ОДИН РАЗ)
                        share_cols = [c for c in df_sheet.columns if c.endswith(" %")]
                        coef = 0.5 if right_category_id == RightCategory.BOTH else 1.0
                        
                        for s_col in share_cols:
                            pay_col = s_col.replace(" %", " Сумма")
                            df_sheet = df_sheet.with_columns(
                                (pl.col("Сумма выплат") * coef * (pl.col(s_col).fill_null(0.0) / 100.0)).alias(pay_col)
                            )
                        
                        # Собираем данные для сводного листа
                        money_cols = [c for c in df_sheet.columns if c.endswith(" Сумма")]
                        summary_row = df_sheet.select([
                            pl.lit(label_code).alias("Правообладатель"),
                            *[pl.col(c).sum().alias(c) for c in money_cols]
                        ])
                        all_summaries.append(summary_row)
                        
                        # Записываем детальный лист
                        df_sheet.write_excel(workbook, worksheet=str(label_code)[:31])

                    # 2. ВНЕ ЦИКЛА: Записываем сводный лист
                    if all_summaries:
                        df_summary = pl.concat(all_summaries, how="diagonal").fill_null(0)
                        df_summary = df_summary.group_by("Правообладатель").sum()
                        df_summary.write_excel(workbook, worksheet="Сводный отчет")

              
                   
                    if df_unclaimed.height > 0:
                        df_unclaimed.write_excel(workbook, worksheet="Нераспределенное")

                return {"status": "success", "output_file": output_path}

        except Exception as e:
            print(f"❌ Ошибка: {str(e)}")
            return {"status": "error", "message": str(e)}
