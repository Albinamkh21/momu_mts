import os
import re
from datetime import datetime
import polars as pl
from sqlalchemy import text, create_engine
from core.celery_app import celery_app
from .utils import clean_null_bytes
from services.broadcaster import TaskProgress
import sys
import uuid


def get_database_url():
    is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "true"
    if is_testing:
        test_url = os.getenv("DATABASE_URL_TEST")
        if test_url:
            return test_url
        return os.getenv("DATABASE_URL", "").replace("/momu", "/momu_test")
    return os.getenv("DATABASE_URL")


DATABASE_URL = get_database_url()

STAGING_TABLE = "staging_contract"

EMAIL_REGEX = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"


def _parse_contact_and_email(raw_val: str | None) -> tuple[str, str]:
    """Разбирает ячейку 'контакты email' на (contact, email)."""
    if not raw_val:
        return "", ""
    text_val = str(raw_val).strip()
    match = re.search(EMAIL_REGEX, text_val)
    if not match:
        return text_val, ""
    email = match.group(0).strip()
    # Убираем найденный email и лишние разделители вокруг него для поля contact
    remainder = re.sub(re.escape(email), "", text_val)
    remainder = re.sub(r"^[\s,;/|:-]+|[\s,;/|:-]+$", "", remainder).strip()
    contact = remainder if remainder else text_val
    return contact, email


def _extract_contract_number(raw_no: str | None) -> int | None:
    """Достаёт первый целочисленный номер договора из строки 'Договор №'."""
    if not raw_no:
        return None
    match = re.search(r"\d+", str(raw_no).replace(" ", ""))
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


# ===========================================================================
#  TASK 1: Загрузка файла в staging_contact
# ===========================================================================

@celery_app.task(name="process_contract_file", bind=True)
def process_contract_file(
    self,
    file_path: str,
    upload_id: str,
    original_filename: str = "",
    user_id: int = None,
):
    task_id = self.request.id
    print(f"🚀 Запуск загрузки договоров [{task_id}] файл: {original_filename or file_path}")
    TaskProgress.emit(upload_id, f"📂 Загрузка файла договоров: {original_filename or file_path}")

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    start_time = datetime.now()
    success = False
    engine = create_engine(DATABASE_URL)

    insert_sql = text(f"""
        INSERT INTO {STAGING_TABLE} (
            contract_number,
            agent_name,
            comments,
            contract_raw_no,
            signed_date,
            valid_until,
            contact,
            email,
            upload_id,
            user_id,
            created_at
        ) VALUES (
            :contract_number,
            :agent_name,
            :comments,
            :contract_raw_no,
            :signed_date,
            :valid_until,
            :contact,
            :email,
            :upload_id,
            :user_id,
            :created_at
        )
    """)

    file_cols = [
        "agent_name",
        "comments",
        "contract_raw_no",
        "signed_date",
        "valid_until",
        "contact",
        "email",
    ]

    try:
        df = pl.read_excel(file_path, infer_schema_length=0)
        df = df.filter(
            ~pl.all_horizontal(
                pl.all().is_null() | (pl.col(pl.String).str.strip_chars() == "")
            )
        )

        if len(df.columns) < len(file_cols):
            raise ValueError(
                f"Ожидалось минимум {len(file_cols)} колонок, получено {len(df.columns)}: {df.columns}"
            )

        total_rows = len(df)
        chunk_size = 50000
        db_batch_size = 2000
        uid_val = uuid.UUID(str(upload_id)) if upload_id else None
        uid_int = int(user_id) if user_id is not None else None

        for i in range(0, total_rows, chunk_size):
            chunk = df.slice(i, chunk_size)
            chunk = chunk.select(chunk.columns[: len(file_cols)])
            chunk.columns = file_cols

            chunk = chunk.with_columns([
                pl.col(c).cast(pl.String, strict=False).fill_null("").str.strip_chars()
                for c in file_cols
            ])
            chunk = clean_null_bytes(chunk)

            rows = [
                {
                    "contract_number": None,
                    "agent_name": r["agent_name"] or None,
                    "comments": r["comments"] or None,
                    "contract_raw_no": r["contract_raw_no"] or None,
                    "signed_date": r["signed_date"] or None,
                    "valid_until": r["valid_until"] or None,
                    "contact": r["contact"] or None,
                    "email": r["email"] or None,
                    "upload_id": uid_val,
                    "user_id": uid_int,
                    "created_at": start_time,
                }
                for r in chunk.to_dicts()
            ]

            with engine.begin() as conn:
                for b in range(0, len(rows), db_batch_size):
                    conn.execute(insert_sql, rows[b : b + db_batch_size])

            print(f"📦 [contracts] Загружен батч: {i} - {i + len(chunk)}")
            TaskProgress.emit(upload_id, f"📦 Загружен батч договоров: {i} - {i + len(chunk)}")

        if os.path.exists(file_path):
            os.remove(file_path)

        success = True
        return {
            "status": "success",
            "total_rows": total_rows,
            "upload_id": upload_id,
        }

    except Exception as e:
        print(f"❌ [contracts] Ошибка загрузки файла: {e}")
        TaskProgress.emit(upload_id, f"❌ Ошибка загрузки файла договоров: {e}")
        raise e

    finally:
        if not success:
            with engine.begin() as clean_conn:
                clean_conn.execute(
                    text(f"DELETE FROM {STAGING_TABLE} WHERE upload_id = :uid"),
                    {"uid": uid_val},
                )
            TaskProgress.emit(upload_id, f"🧹 Staging {STAGING_TABLE} очищен после ошибки")
        engine.dispose()


# ===========================================================================
#  TASK 2: Разбор / синхронизация данных из staging_contact в целевые таблицы
# ===========================================================================

@celery_app.task(name="sync_contracts_from_staging", bind=True)
def sync_contracts_from_staging(self, prev_result=None, upload_id: str = None):
    upload_id = upload_id or (prev_result.get("upload_id") if isinstance(prev_result, dict) else prev_result)
    if not upload_id:
        return {"status": "error", "message": "upload_id не найден"}

    task_id = self.request.id
    success = False

    try:
      
        engine = create_engine(DATABASE_URL)

        with engine.begin() as conn:
            print(f"🔄 [contracts] Начинаем разбор staging_contact для upload_id={upload_id}")
            TaskProgress.emit(upload_id, "🔄 Начинаем разбор загруженных договоров...")

            # Здесь вызываются ваши функции переноса в целевые таблицы (например, контрагенты / договоры)
            # с передачей `conn` и `upload_id`, по аналогии с catalog_tasks_v2.py.
            rows_count = conn.execute(
                text(f"SELECT COUNT(*) FROM {STAGING_TABLE} WHERE upload_id = :uid"),
                {"uid": upload_id},
            ).scalar()

            # Очищаем staging после успешного переноса
            conn.execute(
                text(f"DELETE FROM {STAGING_TABLE} WHERE upload_id = :uid"),
                {"uid": upload_id},
            )

        success = True
        print(f"✅ [contracts] Синхронизация завершена. Обработано строк: {rows_count}")
        TaskProgress.emit(upload_id, f"✅ Разбор договоров завершён. Строк: {rows_count}")
        return {
            "status": "success",
            "upload_id": upload_id,
            "processed_rows": rows_count,
        }

    except Exception as e:
        print(f"❌ [contracts] Ошибка синхронизации: {e}")
        TaskProgress.emit(upload_id, f"❌ Ошибка при разборе договоров: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if not success:
            from sqlalchemy import create_engine
            engine = create_engine(DATABASE_URL)
            with engine.begin() as clean_conn:
                clean_conn.execute(
                    text(f"DELETE FROM {STAGING_TABLE} WHERE upload_id = :uid"),
                    {"uid": upload_id},
                )
            TaskProgress.emit(upload_id, f"🧹 Staging {STAGING_TABLE} очищен после ошибки синхронизации")