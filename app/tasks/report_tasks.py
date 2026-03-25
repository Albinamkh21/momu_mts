import os
import polars as pl
from sqlalchemy import create_engine, text
from core.celery_app import celery_app
from core.constants import RightCategory, FindingSource

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)


def clean_null_bytes(df: pl.DataFrame) -> pl.DataFrame:
    try:
        str_cols = [col for col, dtype in zip(df.columns, df.dtypes) if dtype == pl.Utf8 or dtype == pl.String]
        if str_cols:
            df = df.with_columns([
                pl.col(c).str.replace_all(r"\x00", "", literal=True) for c in str_cols
            ])
        return df
    except Exception as e:
        print(f"⚠️ Ошибка при очистке null-байтов: {e}")
        return df


@celery_app.task(name="process_report_file")
def process_report_file(file_path: str):
    df = None
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File not found"}

    try:
        df = pl.read_excel(file_path, read_options={"skip_rows":0})

        df = df.filter(~pl.all_horizontal(pl.all().is_null()))

        db_columns = [
            "row_number", "label_own_code", "isrc", "track_name",
            "artist_name", "composer", "lyricist", "authors",
            "author_share_pct", "related_share_pct", "play_count",
            "payout_amount", "price_per_play"
        ]

        total_rows = len(df)
        chunk_size = 50000

        for i in range(0, total_rows, chunk_size):
            chunk = df.slice(i, chunk_size)
            
            chunk.columns = db_columns

            chunk = chunk.select(db_columns)
            
            print(f"DEBUG: Chunk shape: {chunk.shape}")
            print(f"DEBUG: Chunk columns: {chunk.columns}")
            print(f"DEBUG: Chunk dtypes: {chunk.dtypes}")
            if len(chunk) > 0:
                print(f"DEBUG: First row: {chunk.row(0)}")
            
            chunk = chunk.with_columns([
                pl.col("*").cast(pl.Utf8).fill_null("")
            ])

            chunk = clean_null_bytes(chunk)

            print(f"DEBUG: After cleaning dtypes: {chunk.dtypes}")
            if len(chunk) > 0:
                print(f"DEBUG: First row after cleaning: {chunk.row(0)}")

            print(f"DEBUG: Column count: {len(chunk.columns)}")
            print(f"DEBUG: Shape: {chunk.shape}")
            chunk.write_database(
                table_name="staging_report",
                connection=DATABASE_URL,
                if_table_exists="append",
                engine="adbc"
            )
            print(f"📦 Загружен батч отчёта: {i} - {i + len(chunk)}")

        if os.path.exists(file_path):
            os.remove(file_path)
            
        return {"status": "success", "total_rows": total_rows}

    except Exception as e:
        print(f"❌ Ошибка воркера (отчёт): {str(e)}")
        return {"status": "error", "message": str(e)}


@celery_app.task(name="update_catalog_dictionaries_from_report")
def update_catalog_dictionaries_from_report():
    """
    Задача для обновления словарей каталога на основе данных из отчёта.
    Заполняет таблицу track_contribution данными о ролях участников.
    """
    try:
        insert_persons_sql = text("""
        INSERT INTO person (full_name)
        SELECT DISTINCT TRIM(name)
        FROM staging_report s
        CROSS JOIN LATERAL (
            SELECT unnest(clean_and_split(s.artist_name)) as name
            UNION SELECT unnest(clean_and_split(s.composer))
            UNION SELECT unnest(clean_and_split(s.lyricist))
            UNION SELECT unnest(clean_and_split(s.authors))
        ) AS all_names
        WHERE name IS NOT NULL AND name != ''
        ON CONFLICT (full_name) DO NOTHING;
        """)
        
        sql_query = text("""
        INSERT INTO track_contribution (track_id, person_id, role)
        SELECT DISTINCT 
            t.id, 
            p.id, 
            role_name
        FROM staging_report s
        JOIN track t ON s.isrc = t.isrc
        CROSS JOIN LATERAL (
            SELECT unnest(clean_and_split(s.artist_name)) as name, 'performer' as role_name
            UNION ALL
            SELECT unnest(clean_and_split(s.composer)), 'composer'
            UNION ALL
            SELECT unnest(clean_and_split(s.lyricist)), 'lyricist'
            UNION ALL
            SELECT unnest(clean_and_split(s.authors)), 'author'
        ) AS unnested_data
        JOIN person p ON p.full_name = unnested_data.name
        ON CONFLICT DO NOTHING;
        """)
        with engine.begin() as connection:
            persons_result = connection.execute(insert_persons_sql)
            persons_added = persons_result.rowcount
            print(f"✅ Добавлено персон: {persons_added}")
            
            result = connection.execute(sql_query)
            rows_affected = result.rowcount
            
        print(f"✅ Обновлены словари каталога. Добавлено записей в track_contribution: {rows_affected}")
        return {"status": "success", "persons_added": persons_added, "track_contributions_added": rows_affected}

    except Exception as e:
        print(f"❌ Ошибка при обновлении словарей каталога: {str(e)}")
        return {"status": "error", "message": str(e)}


@celery_app.task(name="insert_data_into_final_report_table")
def insert_data_into_final_report_table(partner_id: int, right_category_id: int, right_usage_type_id: int, month: int, year: int):
    """
    Задача для переноса данных из staging_report в итоговую таблицу report.
    После вставки экспортирует данные в Excel с информацией о треках и правах.
    """
    try:
        delete_sql = text("""
            DELETE FROM report
            WHERE partner_id = :partner_id
              AND right_category_id = :right_category_id
              AND right_usage_type_id = :right_usage_type_id
              AND report_month = :month
              AND report_year = :year
        """)
        with engine.begin() as connection:
            delete_result = connection.execute(delete_sql, {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year,
            })
            print(f"🗑️ Удалено старых записей из report: {delete_result.rowcount}")

        total_rows_affected = 0

        # === Шаг 1: Поиск по ISRC ===
        insert_by_isrc_sql = text("""
            WITH unique_tracks AS (
                SELECT DISTINCT ON (t.isrc) t.id, t.isrc
                FROM track t
                WHERE t.isrc IN (SELECT s.isrc FROM staging_report_agg s WHERE s.isrc IS NOT NULL)
                ORDER BY t.isrc, t.id ASC
            )
            INSERT INTO report (
                track_id, partner_id, right_category_id, right_usage_type_id, 
                report_month, report_year, play_count, payout_amount, price_per_play, finding_source
            )
            SELECT 
                ut.id,
                :partner_id,
                :right_category_id,
                :right_usage_type_id,
                :month, 
                :year,   
                sum(s.play_count),
                sum(s.payout_amount),
                s.price_per_play,
                :finding_source
            FROM staging_report_agg s
            JOIN unique_tracks ut ON s.isrc = ut.isrc
            WHERE s.isrc IS NOT NULL
            GROUP BY ut.id, s.price_per_play;
        """)

        with engine.begin() as connection:
            result = connection.execute(insert_by_isrc_sql, {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year,
                "finding_source": FindingSource.ISRC
            })
            rows_affected = result.rowcount
            total_rows_affected += rows_affected

        print(f"✅ Шаг 1: Данные перенесены в report по ISRC. Добавлено записей: {rows_affected}")

        # === Шаг 2: Удаление найденных по ISRC из staging_report_agg ===
        delete_by_isrc_sql = text("""
            DELETE FROM staging_report_agg s
            WHERE s.isrc IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM report r
                  JOIN track t ON r.track_id = t.id
                  WHERE t.isrc = s.isrc
                    AND r.partner_id = :partner_id
                    AND r.right_category_id = :right_category_id
                    AND r.right_usage_type_id = :right_usage_type_id
                    AND r.report_month = :month
                    AND r.report_year = :year
              );
        """)

        with engine.begin() as connection:
            del_result = connection.execute(delete_by_isrc_sql, {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year,
            })
            print(f"🗑️ Шаг 2: Удалено из staging_report_agg по ISRC: {del_result.rowcount}")

        # === Шаг 3: Поиск по label_own_code ===
        insert_by_label_sql = text("""
            WITH unique_tracks AS (
                SELECT DISTINCT ON (t.label_own_code) t.id, t.label_own_code
                FROM track t
                WHERE t.label_own_code IN (SELECT s.label_own_code FROM staging_report_agg s WHERE s.label_own_code IS NOT NULL)
                ORDER BY t.label_own_code, t.id ASC
            )
            INSERT INTO report (
                track_id, partner_id, right_category_id, right_usage_type_id, 
                report_month, report_year, play_count, payout_amount, price_per_play, finding_source
            )
            SELECT 
                ut.id,
                :partner_id,
                :right_category_id,
                :right_usage_type_id,
                :month, 
                :year,   
                sum(s.play_count),
                sum(s.payout_amount),
                s.price_per_play,
                :finding_source
            FROM staging_report_agg s
            JOIN unique_tracks ut ON s.label_own_code = ut.label_own_code
            WHERE s.label_own_code IS NOT NULL
            GROUP BY ut.id, s.price_per_play;
        """)

        with engine.begin() as connection:
            result = connection.execute(insert_by_label_sql, {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year,
                "finding_source": FindingSource.LABEL_OWN_CODE
            })
            rows_affected = result.rowcount
            total_rows_affected += rows_affected

        print(f"✅ Шаг 3: Данные перенесены в report по label_own_code. Добавлено записей: {rows_affected}")

        # === Шаг 4: Удаление найденных по label_own_code из staging_report_agg ===
        delete_by_label_sql = text("""
            DELETE FROM staging_report_agg s
            WHERE s.label_own_code IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM report r
                  JOIN track t ON r.track_id = t.id
                  WHERE t.label_own_code = s.label_own_code
                    AND r.partner_id = :partner_id
                    AND r.right_category_id = :right_category_id
                    AND r.right_usage_type_id = :right_usage_type_id
                    AND r.report_month = :month
                    AND r.report_year = :year
              );
        """)

        with engine.begin() as connection:
            del_result = connection.execute(delete_by_label_sql, {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year,
            })
            print(f"🗑️ Шаг 4: Удалено из staging_report_agg по label_own_code: {del_result.rowcount}")

        # === Шаг 5: Поиск по track_name + author ===
        insert_by_author_sql = text("""
            WITH unique_tracks AS (
                SELECT DISTINCT ON (s.track_name, s.authors) t.id, s.track_name, s.authors
                FROM staging_report_agg s
                JOIN track t ON t.title = s.track_name
                WHERE s.authors IS NOT NULL AND s.authors != ''
                  AND EXISTS (
                      SELECT 1
                      FROM track_contribution tc
                      JOIN person p ON p.id = tc.person_id
                      WHERE tc.track_id = t.id
                        AND tc.role = 'author'
                        AND p.full_name = ANY(clean_and_split(s.authors))
                  )
                ORDER BY s.track_name, s.authors, t.id ASC
            )
            INSERT INTO report (
                track_id, partner_id, right_category_id, right_usage_type_id,
                report_month, report_year, play_count, payout_amount, price_per_play, finding_source
            )
            SELECT
                ut.id,
                :partner_id,
                :right_category_id,
                :right_usage_type_id,
                :month,
                :year,
                s.play_count,
                s.payout_amount,
                s.price_per_play,
                :finding_source
            FROM staging_report_agg s
            JOIN unique_tracks ut ON ut.track_name = s.track_name AND ut.authors = s.authors;
        """)

        with engine.begin() as connection:
            result = connection.execute(insert_by_author_sql, {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year,
                "finding_source": FindingSource.NAME_AUTHOR
            })
            rows_affected = result.rowcount
            total_rows_affected += rows_affected

        print(f"✅ Шаг 5: Данные перенесены в report по NAME+AUTHOR. Добавлено записей: {rows_affected}")

        # === Шаг 6: Удаление найденных по track_name + author из staging_report_agg ===
        delete_by_author_sql = text("""
            DELETE FROM staging_report_agg s
            WHERE s.authors IS NOT NULL AND s.authors != ''
              AND EXISTS (
                  SELECT 1 FROM report r
                  JOIN track t ON r.track_id = t.id
                  WHERE t.title = s.track_name
                    AND r.partner_id = :partner_id
                    AND r.right_category_id = :right_category_id
                    AND r.right_usage_type_id = :right_usage_type_id
                    AND r.report_month = :month
                    AND r.report_year = :year
                    AND EXISTS (
                        SELECT 1 FROM track_contribution tc
                        JOIN person p ON p.id = tc.person_id
                        WHERE tc.track_id = t.id
                          AND tc.role = 'author'
                          AND p.full_name = ANY(clean_and_split(s.authors))
                    )
              );
        """)

        with engine.begin() as connection:
            del_result = connection.execute(delete_by_author_sql, {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year,
            })
            print(f"🗑️ Шаг 6: Удалено из staging_report_agg по NAME+AUTHOR: {del_result.rowcount}")

        rows_affected = total_rows_affected
        print(f"✅ Итого добавлено записей в report: {total_rows_affected}")







        # Экспорт данных в Excel
        print("📤 Начинаем экспорт отчёта в Excel...")
        base_query = text("""
        SELECT DISTINCT
            t.id AS track_id,
            t.label_own_code AS "Код лейбла",
            t.isrc AS "Код ISRC",
            t.title AS "Название трека",
            (SELECT string_agg(DISTINCT p.full_name, ', ')
             FROM track_contribution tc JOIN person p ON p.id = tc.person_id
             WHERE tc.track_id = t.id AND tc.role = 'performer'
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
             WHERE tc.track_id = t.id AND tc.role = 'author'
            ) AS "Авторы",
            r.play_count AS "Кол-во прослушиваний",
            r.payout_amount AS "Сумма выплат",
            r.price_per_play AS "Цена за прослушивание",
            fs.code AS "Источник совпадения"
        FROM report r
        JOIN track t ON r.track_id = t.id
        JOIN finding_source fs ON fs.id = r.finding_source
        WHERE r.partner_id = :partner_id
          AND r.right_category_id = :right_category_id
          AND r.right_usage_type_id = :right_usage_type_id
          AND r.report_month = :month
          AND r.report_year = :year
        ORDER BY t.label_own_code, t.title;
        """)

        rights_query = text("""
        SELECT
            tr.track_id,
            rc.name AS category,
            rh.name AS right_holder_name,
            tr.share_percentage,
            ROW_NUMBER() OVER (PARTITION BY tr.track_id, rc.name ORDER BY rh.name) AS rn
        FROM track_right tr
        JOIN right_category rc ON rc.id = tr.right_category_id
        JOIN right_holder rh ON rh.id = tr.right_holder_id
        WHERE tr.track_id IN (
            SELECT r.track_id FROM report r
            WHERE r.partner_id = :partner_id
              AND r.right_category_id = :right_category_id
              AND r.right_usage_type_id = :right_usage_type_id
              AND r.report_month = :month
              AND r.report_year = :year
        )
        ORDER BY tr.track_id, rc.name, rn;
        """)

        report_params = {
            "partner_id": partner_id,
            "right_category_id": right_category_id,
            "right_usage_type_id": right_usage_type_id,
            "month": month,
            "year": year,
        }

        with engine.connect() as conn:
            df_base = pl.read_database(query=base_query, connection=conn, infer_schema_length=None, execute_options={"parameters": report_params})
            df_rights = pl.read_database(query=rights_query, connection=conn, infer_schema_length=None, execute_options={"parameters": report_params})

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

        # Разделяем права по категориям
        df_author = df_rights.filter(pl.col("category") == "Author")
        df_related = df_rights.filter(pl.col("category") == "Related")

        max_author = df_author.select(pl.col("rn").max()).item() if len(df_author) > 0 else 0
        max_related = df_related.select(pl.col("rn").max()).item() if len(df_related) > 0 else 0

        # Добавляем столбцы для каждого правообладателя (авторские права)
        for i in range(1, (max_author or 0) + 1):
            author_i = df_author.filter(pl.col("rn") == i).select([
                pl.col("track_id"),
                pl.col("right_holder_name").alias(f"Правообладатель (авторские) {i}"),
                pl.col("share_percentage").alias(f"Доля авторских прав {i}, %"),
            ])
            df_base = df_base.join(author_i, on="track_id", how="left")

        # Добавляем столбцы для каждого правообладателя (смежные права)
        for i in range(1, (max_related or 0) + 1):
            related_i = df_related.filter(pl.col("rn") == i).select([
                pl.col("track_id"),
                pl.col("right_holder_name").alias(f"Правообладатель (смежные) {i}"),
                pl.col("share_percentage").alias(f"Доля смежных прав {i}, %"),
            ])
            df_base = df_base.join(related_i, on="track_id", how="left")

        df = df_base.drop("track_id")

        storage_dir = "/app/storage"
        os.makedirs(storage_dir, exist_ok=True)
        filename = f"report_{year}_{month}_{partner_code}_{right_category_name}_{right_usage_type_code}.xlsx"
        output_path = os.path.join(storage_dir, filename)
        df.write_excel(output_path)

        print(f"✅ Отчёт экспортирован в файл: {output_path}")
        print(f"📊 Всего строк в файле: {len(df)}")

        return {
            "status": "success",
            "report_records_added": rows_affected,
            "rows_exported": len(df),
            "output_file": output_path
        }

    except Exception as e:
        print(f"❌ Ошибка при переносе данных в report: {str(e)}")
        return {"status": "error", "message": str(e)}


@celery_app.task(name="process_full_report_pipeline")
def process_full_report_pipeline(file_path: str, partner_id: int, right_category_id: int, right_usage_type_id: int, month: int, year: int):
    """
    Оркестратор: последовательно выполняет весь пайплайн обработки отчёта.
    Каждая задача запускается только при успехе предыдущей.
    """
    steps_completed = []

    # === Шаг 0: Очистка staging таблиц ===
    try:
        print("🧹 Шаг 0: Очистка staging_report и staging_report_agg...")
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE TABLE staging_report;"))
            connection.execute(text("CREATE TABLE IF NOT EXISTS staging_report_agg (id BIGSERIAL PRIMARY KEY, label_own_code TEXT, isrc TEXT, track_name TEXT, artist_name TEXT, authors TEXT, play_count BIGINT DEFAULT 0, payout_amount NUMERIC(20,8) DEFAULT 0.0, price_per_play NUMERIC(20,8) DEFAULT 0.0);"))
            connection.execute(text("TRUNCATE TABLE staging_report_agg;"))
        print("✅ Шаг 0 завершён: staging таблицы очищены")
        steps_completed.append("clean_staging")
    except Exception as e:
        print(f"❌ Шаг 0 (очистка staging): {e}")
        return {"status": "error", "step": "clean_staging", "message": str(e), "steps_completed": steps_completed}

    # === Шаг 1: Загрузка и парсинг файла ===
    print("📥 Шаг 1: Загрузка и парсинг файла (process_report_file)...")
    result = process_report_file(file_path)
    if result.get("status") != "success":
        print(f"❌ Шаг 1 (process_report_file) завершился с ошибкой: {result.get('message')}")
        return {"status": "error", "step": "process_report_file", "message": result.get("message"), "steps_completed": steps_completed}
    print(f"✅ Шаг 1 завершён: process_report_file — загружено строк: {result.get('total_rows')}")
    steps_completed.append("process_report_file")

    # === Шаг 2: Обновление словарей каталога ===
    print("📚 Шаг 2: Обновление словарей каталога (update_catalog_dictionaries_from_report)...")
    result = update_catalog_dictionaries_from_report()
    if result.get("status") != "success":
        print(f"❌ Шаг 2 (update_catalog_dictionaries_from_report) завершился с ошибкой: {result.get('message')}")
        return {"status": "error", "step": "update_catalog_dictionaries_from_report", "message": result.get("message"), "steps_completed": steps_completed}
    print(f"✅ Шаг 2 завершён: update_catalog_dictionaries_from_report — персон: {result.get('persons_added')}, контрибуций: {result.get('track_contributions_added')}")
    steps_completed.append("update_catalog_dictionaries_from_report")

    # === Шаг 3: Группировка данных ===
    print("📊 Шаг 3: Группировка данных (group_report_data)...")
    result = group_report_data()
    if result.get("status") != "success":
        print(f"❌ Шаг 3 (group_report_data) завершился с ошибкой: {result.get('message')}")
        return {"status": "error", "step": "group_report_data", "message": result.get("message"), "steps_completed": steps_completed}
    print(f"✅ Шаг 3 завершён: group_report_data — агрегировано: {result.get('rows_aggregated')}, экспортировано: {result.get('rows_exported')}")
    steps_completed.append("group_report_data")

    # === Шаг 4: Проверка sum(payout_amount) ===
    try:
        print("🔍 Шаг 4: Проверка sum(payout_amount) staging_report == staging_report_agg...")
        with engine.connect() as connection:
            row = connection.execute(text("""
                SELECT
                    (SELECT COALESCE(SUM(COALESCE(NULLIF(REPLACE(payout_amount, ',', '.'), ''), '0')::NUMERIC(20,8)), 0) FROM staging_report) AS sum_staging,
                    (SELECT COALESCE(SUM(payout_amount), 0) FROM staging_report_agg) AS sum_agg
            """)).fetchone()
            sum_staging = row.sum_staging
            sum_agg = row.sum_agg
        if sum_staging != sum_agg:
            msg = f"Суммы payout_amount не совпадают: staging_report={sum_staging}, staging_report_agg={sum_agg}"
            print(f"❌ Шаг 4: {msg}")
            return {"status": "error", "step": "verify_payout_amount", "message": msg, "steps_completed": steps_completed, "sum_staging": str(sum_staging), "sum_agg": str(sum_agg)}
        print(f"✅ Шаг 4 завершён: суммы совпадают ({sum_staging})")
        steps_completed.append("verify_payout_amount")
    except Exception as e:
        print(f"❌ Шаг 4 (проверка payout_amount): {e}")
        return {"status": "error", "step": "verify_payout_amount", "message": str(e), "steps_completed": steps_completed}

    # === Шаг 5: Перенос данных в итоговую таблицу report ===
    print("📝 Шаг 5: Перенос данных в итоговую таблицу (insert_data_into_final_report_table)...")
    result = insert_data_into_final_report_table(partner_id, right_category_id, right_usage_type_id, month, year)
    if result.get("status") != "success":
        print(f"❌ Шаг 5 (insert_data_into_final_report_table) завершился с ошибкой: {result.get('message')}")
        return {"status": "error", "step": "insert_data_into_final_report_table", "message": result.get("message"), "steps_completed": steps_completed}
    print(f"✅ Шаг 5 завершён: insert_data_into_final_report_table — записей: {result.get('report_records_added')}, экспортировано: {result.get('rows_exported')}")
    steps_completed.append("insert_data_into_final_report_table")

    print("🎉 Пайплайн завершён успешно!")
    return {
        "status": "success",
        "steps_completed": steps_completed,
        "final_result": result
    }


@celery_app.task(name="group_report_data")
def group_report_data():
    """
    Задача для группировки данных отчёта и сохранения в staging_report_agg,
    а затем экспорта в файл report_avg.xlsx
    """
    try:
        with engine.begin() as connection:
            print("📋 Начинаем группировку данных отчёта...")
            
            create_table_sql = text("""
            CREATE TABLE IF NOT EXISTS staging_report_agg (
                id BIGSERIAL PRIMARY KEY,
                label_own_code TEXT,
                isrc TEXT,
                track_name TEXT,
                artist_name TEXT,
                authors TEXT,
                play_count BIGINT DEFAULT 0,
                payout_amount NUMERIC(20, 8) DEFAULT 0.0,
                price_per_play NUMERIC(20, 8) DEFAULT 0.0
              
            );
            """)
            connection.execute(create_table_sql)
            print("✅ Таблица staging_report_agg готова")
            
            truncate_sql = text("TRUNCATE TABLE staging_report_agg;")
            connection.execute(truncate_sql)
            print("✅ Таблица staging_report_agg очищена")
            
            insert_agg_sql = text("""
                INSERT INTO staging_report_agg (
                    label_own_code,
                    isrc,
                    track_name,
                    artist_name,
                    authors,
                    play_count,
                    payout_amount,
                    price_per_play
                )
                SELECT 
                    label_own_code,
                    isrc,   
                    track_name,
                    artist_name,
                    authors,
                    SUM(COALESCE(NULLIF(play_count, '')::INT, 0)) as total_plays,
                    SUM(COALESCE(NULLIF(payout_amount, '')::NUMERIC(20, 8), 0)) as total_payout,
                    AVG(NULLIF(COALESCE(NULLIF(price_per_play, '')::NUMERIC(20, 8), 0), 0)) as avg_price
                FROM staging_report
                        GROUP BY label_own_code, isrc, track_name, artist_name, authors;
                """)
            
            result = connection.execute(insert_agg_sql)
            rows_inserted = result.rowcount
            print(f"✅ Агрегировано и вставлено записей: {rows_inserted}")


            


        
        print("📤 Начинаем экспорт в Excel...")
        export_query = """
            SELECT 
                label_own_code,
                isrc,
                track_name,
                artist_name,
                authors,
                play_count,
                payout_amount,
                price_per_play
            
            FROM staging_report_agg
            ORDER BY label_own_code, isrc, track_name, artist_name;
            """
        
        with engine.connect() as conn:
            df = pl.read_database(
                query=export_query,
                connection=conn,
                infer_schema_length=None
            )
            
            storage_dir = "/app/storage"
            os.makedirs(storage_dir, exist_ok=True)
            
            output_path = os.path.join(storage_dir, "report_avg.xlsx")
            df.write_excel(output_path)
            
        print(f"✅ Данные экспортированы в файл: {output_path}")
        print(f"📊 Всего строк в файле: {len(df)}")
        
        return {
            "status": "success", 
            "rows_aggregated": rows_inserted,
            "rows_exported": len(df),
            "output_file": output_path
        }

    except Exception as e:
        print(f"❌ Ошибка при группировке данных отчёта: {str(e)}")
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

        query = """ select  track_name, artist_name, authors, isrc, label_own_code, payout_amount  from staging_report_agg  order by payout_amount desc;
          """

        with engine.connect() as conn:
            df = pl.read_database(
                query=query,
                connection=conn,
                infer_schema_length=None
            )

        print(f"🔍 Найдено потерянных треков: {len(df)}")

        storage_dir = "/app/storage"
        os.makedirs(storage_dir, exist_ok=True)
        output_path = os.path.join(storage_dir, "lost_tracks.xlsx")
        df.write_excel(output_path)

        print(f"✅ Данные экспортированы в файл: {output_path}")

        return {
            "status": "success",
            "lost_tracks_count": len(df),
            "output_file": output_path
        }

    except Exception as e:
        print(f"❌ Ошибка при поиске потерянных треков: {str(e)}")
        return {"status": "error", "message": str(e)}