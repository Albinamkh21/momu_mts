import os
import polars as pl
from sqlalchemy import create_engine, text
from core.celery_app import celery_app

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
    """
    try:
        insert_report_sql = text("""
        INSERT INTO report (
            track_id, 
            partner_id, 
            right_category_id, 
            right_usage_type_id, 
            report_month, 
            report_year, 
            play_count, 
            payout_amount, 
            price_per_play, 
            author_share_pct, 
            related_share_pct
        )
        SELECT 
            t.id AS track_id,
            :partner_id,
            :right_category_id,
            :right_usage_type_id,
            :month, 
            :year,   
            COALESCE(s.play_count::INT, 0),
            COALESCE(REPLACE(s.payout_amount, ',', '.')::NUMERIC(20, 4), 0),
            COALESCE(REPLACE(s.price_per_play, ',', '.')::NUMERIC(20, 6), 0),
            COALESCE(REPLACE(s.author_share_pct, ',', '.')::NUMERIC(5, 2), 0),
            COALESCE(REPLACE(s.related_share_pct, ',', '.')::NUMERIC(5, 2), 0)
        FROM staging_report s
        JOIN track t ON s.isrc = t.isrc
        """)

        with engine.begin() as connection:
            result = connection.execute(insert_report_sql, {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year
            })
            rows_affected = result.rowcount
            
        print(f"✅ Данные перенесены в итоговую таблицу report. Добавлено записей: {rows_affected}")
        return {"status": "success", "report_records_added": rows_affected}

    except Exception as e:
        print(f"❌ Ошибка при переносе данных в report: {str(e)}")
        return {"status": "error", "message": str(e)}


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
                track_name TEXT,
                artist_name TEXT,
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
                track_name,
                artist_name,
                play_count,
                payout_amount,
                price_per_play
            )
            SELECT 
                label_own_code,
                track_name,
                artist_name,
                SUM(COALESCE(NULLIF(play_count, '')::INT, 0)) as total_plays,
                SUM(COALESCE(NULLIF(payout_amount, '')::NUMERIC(20, 8), 0)) as total_payout,
                AVG(NULLIF(COALESCE(NULLIF(price_per_play, '')::NUMERIC(20, 8), 0), 0)) as avg_price
            FROM staging_report
                    GROUP BY label_own_code, track_name, artist_name;
            """)
            
            result = connection.execute(insert_agg_sql)
            rows_inserted = result.rowcount
            print(f"✅ Агрегировано и вставлено записей: {rows_inserted}")
        
        print("📤 Начинаем экспорт в Excel...")
        export_query = """
        SELECT 
            label_own_code,
            track_name,
            artist_name,
            play_count,
            payout_amount,
            price_per_play
        
        FROM staging_report_agg
        ORDER BY label_own_code , track_name, artist_name;
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