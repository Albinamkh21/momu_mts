from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional as TypingOptional
import shutil
import os
from uuid import uuid4
from celery import chain
from sqlalchemy import text
from sqlalchemy.orm import Session
from core.database import sync_engine, SessionLocal
from tasks.report_tasks import (
    process_report_file,
    insert_data_into_final_report_table, group_report_data, find_lost_track,
    process_full_report_pipeline, normalize_person_data, normalize_staging_report_agg, normalize_data,
    export_report_to_excel, create_report_task, calculate_and_save_distribution_sql, export_report_distribution_to_excel
)
from __schemas.reports import ReportHistoryItem, ReportDeleteRequest
from services.report_history_service import ReportHistoryService

router = APIRouter()
STORAGE_DIR = "/app/storage"

class ReportDataRequest(BaseModel):
    partner_id: int
    right_category_id: int
    right_usage_type_id: int
    month: int = Field(..., ge=1, le=12)
    year: int


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── История отчётов (report history tab) ────────────────────────────────────
# Controller (этот роутер) -> ReportHistoryService -> ReportRepository

@router.get("/report", response_model=List[ReportHistoryItem])
async def get_report_history(
    partner_id: TypingOptional[int] = Query(None),
    right_category_id: TypingOptional[int] = Query(None),
    right_usage_type_id: TypingOptional[int] = Query(None),
    year_from: TypingOptional[int] = Query(None),
    year_to: TypingOptional[int] = Query(None),
    month_from: TypingOptional[int] = Query(None, ge=1, le=12),
    month_to: TypingOptional[int] = Query(None, ge=1, le=12),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    response: Response = None,
    db: Session = Depends(get_db),
):
    """Список отчётов из таблицы report (с фильтрами по партнёру/категории/типу/периоду и сортировкой)."""
    service = ReportHistoryService(db)
    items, total = service.list_reports(
        partner_id=partner_id,
        right_category_id=right_category_id,
        right_usage_type_id=right_usage_type_id,
        year_from=year_from,
        year_to=year_to,
        month_from=month_from,
        month_to=month_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return items


@router.delete("/report")
async def delete_report_history(body: ReportDeleteRequest, db: Session = Depends(get_db)):
    """Удаление одного или нескольких отчётов по id."""
    try:
        deleted = ReportHistoryService(db).delete_reports(body.ids)
        return {"deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/partners")
async def get_partners():
    """Return list of partners as id/label (code + service_name)."""
    try:
        with sync_engine.connect() as conn:
            rows = conn.execute(text("SELECT id, COALESCE(code, id::text) || ' - ' || service_name AS label FROM partners ORDER BY service_name"))
            result = [{"id": r.id, "label": r.label} for r in rows]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/right_categories")
async def get_right_categories():
    """Return right categories."""
    try:
        with sync_engine.connect() as conn:
            rows = conn.execute(text("SELECT id, name AS label FROM right_category ORDER BY name"))
            result = [{"id": r.id, "label": r.label} for r in rows]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/right_usage_types")
async def get_right_usage_types():
    """Return right usage types."""
    try:
        with sync_engine.connect() as conn:
            rows = conn.execute(text("SELECT id, code || ' - ' || name AS label FROM right_usage_type ORDER BY id"))
            result = [{"id": r.id, "label": r.label} for r in rows]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labels")
async def get_labels():
    """Return labels for filtering reports."""
    try:
        with sync_engine.connect() as conn:
            rows = conn.execute(text("SELECT id, name AS label FROM label ORDER BY name"))
            result = [{"id": r.id, "label": r.label} for r in rows]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel
from typing import List, Optional


class PartnerItem(BaseModel):
    organization_name: str
    service_name: str
    contract_number: Optional[str] = None
    right_usage_type_id: Optional[int] = None
    note: Optional[str] = None
    code: Optional[str] = None


class RightCategoryItem(BaseModel):
    name: str


class RightUsageTypeItem(BaseModel):
    code: str
    name: Optional[str] = None
    description: Optional[str] = None


@router.post("/fill_partners")
async def fill_partners(items: List[PartnerItem]):
    """Upsert partners from provided list. Matches on (organization_name, service_name)."""
    try:
        inserted = 0
        updated = 0
        with sync_engine.begin() as conn:
            for it in items:
                # check exists
                row = conn.execute(text("SELECT id FROM partners WHERE organization_name = :org AND service_name = :svc"), {
                    "org": it.organization_name,
                    "svc": it.service_name,
                }).fetchone()
                if row:
                    conn.execute(text(
                        "UPDATE partners SET contract_number = :contract_number, right_usage_type_id = :rut, note = :note, code = COALESCE(:code, code) WHERE id = :id"
                    ), {
                        "contract_number": it.contract_number,
                        "rut": it.right_usage_type_id,
                        "note": it.note,
                        "code": it.code,
                        "id": row.id,
                    })
                    updated += 1
                else:
                    conn.execute(text(
                        "INSERT INTO partners (organization_name, service_name, contract_number, right_usage_type_id, note, code) VALUES (:org, :svc, :contract_number, :rut, :note, :code)"
                    ), {
                        "org": it.organization_name,
                        "svc": it.service_name,
                        "contract_number": it.contract_number,
                        "rut": it.right_usage_type_id,
                        "note": it.note,
                        "code": it.code,
                    })
                    inserted += 1

        return {"inserted": inserted, "updated": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fill_right_categories")
async def fill_right_categories(items: List[RightCategoryItem]):
    """Insert missing right categories from provided list (no-op if exists)."""
    try:
        inserted = 0
        with sync_engine.begin() as conn:
            for it in items:
                # insert only if not exists
                conn.execute(text(
                    "INSERT INTO right_category (name) SELECT :name WHERE NOT EXISTS (SELECT 1 FROM right_category WHERE name = :name)"
                ), {"name": it.name})
                # rowcount not reliable for this construct; compute existence after
                r = conn.execute(text("SELECT id FROM right_category WHERE name = :name"), {"name": it.name}).fetchone()
                if r:
                    inserted += 1

        return {"processed": len(items), "inserted_or_existing": inserted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fill_right_usage_types")
async def fill_right_usage_types(items: List[RightUsageTypeItem]):
    """Upsert right usage types matching on code."""
    try:
        inserted = 0
        updated = 0
        with sync_engine.begin() as conn:
            for it in items:
                row = conn.execute(text("SELECT id FROM right_usage_type WHERE code = :code"), {"code": it.code}).fetchone()
                if row:
                    conn.execute(text(
                        "UPDATE right_usage_type SET name = COALESCE(:name, name), description = COALESCE(:description, description) WHERE id = :id"
                    ), {"name": it.name, "description": it.description, "id": row.id})
                    updated += 1
                else:
                    conn.execute(text(
                        "INSERT INTO right_usage_type (code, name, description) VALUES (:code, :name, :description)"
                    ), {"code": it.code, "name": it.name, "description": it.description})
                    inserted += 1

        return {"inserted": inserted, "updated": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_report(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_id = str(uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(STORAGE_DIR, f"{file_id}{file_ext}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Последовательное выполнение задач. Если любая упадет, следующая не запустится
    workflow = chain(
            process_report_file.s(file_path) 
          
        )
 
    task_result = workflow.apply_async()
    #task_result = process_report_file.delay(file_path)



    return {
        "message": "Файл отчёта принят и поставлен в очередь на обработку",
        "task_id": task_result.id,
        "filename": file.filename
    }


@router.post("/get_report_data")
async def get_report_data_endpoint(
    file: UploadFile = File(...),
    partner_id: int = Form(...),
    right_category_id: int = Form(...),
    right_usage_type_id: int = Form(...),
    month: int = Form(..., ge=1, le=12),
    year: int = Form(...),
    group_data: bool = Form(True),
):
    """
    Полный пайплайн обработки отчёта:
    1. Очистка staging_report и staging_report_agg
    2. Загрузка файла и парсинг (process_report_file)
   
    4. Группировка данных (group_report_data)
    5. Проверка sum(payout_amount) staging_report == staging_report_agg
    6. Перенос в итоговую таблицу report (insert_data_into_final_report_table)
    """
    if not file.filename.endswith(('.xlsx', '.csv')):
        raise HTTPException(status_code=400, detail="Неверный тип файла. Допустимы .xlsx и .csv")

    file_id = str(uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(STORAGE_DIR, f"{file_id}{file_ext}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        task_result = process_full_report_pipeline.delay(
            file_path, partner_id, right_category_id,
            right_usage_type_id, month, year, group_data
        )
        return {
            "message": "Полный пайплайн обработки отчёта запущен",
            "task_id": task_result.id,
            "filename": file.filename,
            "params": {
                "partner_id": partner_id,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "month": month,
                "year": year,
                "group_data": group_data
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске пайплайна: {str(e)}")






@router.post("/group_report_data")
async def group_report_data_endpoint():
    """
    Эндпоинт для группировки данных отчёта.
    Агрегирует данные из staging_report в staging_report_agg и экспортирует в Excel.
    """
    try:
        # Запускаем задачу группировки данных
        task_result = group_report_data.delay()
        
        return {
            "message": "Задача группировки данных отчёта запущена",
            "task_id": task_result.id,
            "description": "Данные будут агрегированы из staging_report в staging_report_agg и экспортированы в файл report_avg.xlsx"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске группировки: {str(e)}")


@router.post("/find_lost_track")
async def find_lost_track_endpoint():
    """
    Эндпоинт для поиска треков из staging_report_agg, которые не найдены в таблице track.
    Результат экспортируется в файл lost_tracks.xlsx.
    """
    try:
        task_result = find_lost_track.delay()

        return {
            "message": "Задача поиска потерянных треков запущена",
            "task_id": task_result.id,
            "description": "Результат будет экспортирован в файл lost_tracks.xlsx"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске поиска потерянных треков: {str(e)}")


@router.post("/normalize_person_data")
async def normalize_person_data_endpoint(
    table_name: str = Form("person"),
    column_name: str = Form("full_name"),
):
    """
    Нормализация данных в указанной таблице:
    заполняет {column_name}_tokens и {column_name}_norm_key на основе {column_name}.
    """
    try:
        task_result = normalize_person_data.delay(table_name, column_name)

        return {
            "message": f"Задача нормализации {table_name}.{column_name} запущена",
            "task_id": task_result.id,
            "description": f"Поля {column_name}_tokens и {column_name}_norm_key будут заполнены в таблице {table_name}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске нормализации: {str(e)}")


@router.post("/normalize_data")
async def normalize_data_endpoint(
    table_name: str = Form("person"),
    column_name: str = Form("full_name"),
):
    """
    Нормализация данных в указанной таблице:
    заполняет {column_name}_tokens и {column_name}_norm_key на основе {column_name}.
    """
    try:
        task_result = normalize_data.delay(table_name, column_name)

        return {
            "message": f"Задача нормализации {table_name}.{column_name} запущена",
            "task_id": task_result.id,
            "description": f"Поля {column_name}_tokens и {column_name}_norm_key будут заполнены в таблице {table_name}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске нормализации: {str(e)}")


@router.post("/normalize_staging_report_agg")
async def normalize_staging_report_agg_endpoint():
    """
    Нормализация artist_name и authors в staging_report_agg:
    заполняет artist_name_tokens, artist_name_norm_key_full,
    authors_tokens, authors_norm_key_full.
    """
    try:
        task_result = normalize_staging_report_agg.delay()

        return {
            "message": "Задача нормализации staging_report_agg запущена",
            "task_id": task_result.id,
            "description": "Нормализованные поля artist_name и authors будут заполнены"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске нормализации staging: {str(e)}")


@router.post("/export_report_to_excel")
async def export_report_to_excel_endpoint(
    partner_id: int = Form(...),
    right_category_id: int = Form(...),
    right_usage_type_id: int = Form(...),
    month: int = Form(..., ge=1, le=12),
    year: int = Form(...),
):
    """
    Экспорт данных из staging_report_ids / staging_report_agg в Excel.
    Использует уже заполненные staging-таблицы (для тестирования без полного пайплайна).
    """
    try:
        task_result = export_report_to_excel.delay(
            partner_id, right_category_id, right_usage_type_id, month, year
        )
        return {
            "message": "Задача экспорта отчёта в Excel запущена",
            "task_id": task_result.id,
            "description": "Результат будет экспортирован в файл report_<year>_<month>_<partner>_<category>_<usage_type>.xlsx",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске экспорта: {str(e)}")


@router.post("/create_report")
async def create_report(
    partner_id: str = Form(default=""),
    year: int = Form(...),
    month_from: int = Form(..., ge=1, le=12),
    month_to: int = Form(..., ge=1, le=12),
    right_category_id: int = Form(...),
    right_usage_type_id: int = Form(...),
    label_ids: str = Form(default=""),
):
    """
    Создание отчёта с собранными данными и экспортом в файл.
    
    Параметры:
    - partner_id: ID партнёра (опционально)
    - year: год отчёта
    - month_from: начальный месяц (1-12)
    - month_to: конечный месяц (1-12)
    - right_category_id: ID категории прав
    - right_usage_type_id: ID типа использования прав
    - label_ids: список ID лейблов через запятую (если пусто, то все лейблы)
    """
    try:
        # Преобразование partner_id если он передан
        partner_id_int = None
        if partner_id and str(partner_id).strip():
            try:
                partner_id_int = int(partner_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="partner_id должен быть числом")
        
        # Преобразование label_ids из строки в список
        labels_list = None
        if label_ids and label_ids.strip():
            try:
                labels_list = [int(lid.strip()) for lid in label_ids.split(",") if lid.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="label_ids должны быть числами через запятую")

        task_result = create_report_task.delay(
            partner_id_int, year, month_from, month_to, right_category_id, right_usage_type_id, labels_list
        )
        return {
            "message": "Задача создания отчёта запущена",
            "task_id": task_result.id,
            "params": {
                "partner_id": partner_id_int,
                "year": year,
                "month_from": month_from,
                "month_to": month_to,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "label_ids": labels_list if labels_list else "все лейблы"
            }
        }
        return {
            "message": "Задача создания отчёта запущена",
            "task_id": task_result.id,
            "params": {
                "year": year,
                "month_from": month_from,
                "month_to": month_to,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "label_ids": labels_list if labels_list else "все лейблы"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске создания отчёта: {str(e)}")


@router.post("/calculate_and_save_distribution")
async def calculate_and_save_distribution_endpoint(
    year: int = Form(...),
    month_from: int = Form(..., ge=1, le=12),
    month_to: int = Form(..., ge=1, le=12),
    right_category_id: int = Form(...),
    right_usage_type_id: int = Form(...),
    label_ids: str = Form(default=""),
):
    """
    Расчет распределения выплат по правообладателям напрямую в SQL.
    
    Параметры:
    - year: год отчёта
    - month_from: начальный месяц (1-12)
    - month_to: конечный месяц (1-12)
    - right_category_id: ID категории прав
    - right_usage_type_id: ID типа использования прав
    - label_ids: список ID лейблов через запятую (если пусто, то все лейблы)
    """
    try:
        # Преобразование label_ids из строки в список
        labels_list = None
        if label_ids and label_ids.strip():
            try:
                labels_list = [int(lid.strip()) for lid in label_ids.split(",") if lid.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="label_ids должны быть числами через запятую")

        from celery import current_task
        task_id = current_task.request.id if current_task else None

        task_result = calculate_and_save_distribution_sql.delay(
            task_id, year, month_from, month_to, right_category_id, right_usage_type_id, labels_list
        )
        return {
            "message": "Задача расчета распределения запущена",
            "task_id": task_result.id,
            "params": {
                "year": year,
                "month_from": month_from,
                "month_to": month_to,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "label_ids": labels_list if labels_list else "все лейблы"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске расчета распределения: {str(e)}")


@router.post("/export_report_distribution")
async def export_report_distribution_endpoint(
    year: int = Form(...),
    month_from: int = Form(..., ge=1, le=12),
    month_to: int = Form(..., ge=1, le=12),
    right_category_id: int = Form(...),
    right_usage_type_id: int = Form(...),
    label_ids: str = Form(default=""),
):
    """
    Экспорт распределенных выплат по правообладателям из report_distribution в Excel.
    
    Параметры:
    - year: год отчёта
    - month_from: начальный месяц (1-12)
    - month_to: конечный месяц (1-12)
    - right_category_id: ID категории прав
    - right_usage_type_id: ID типа использования прав
    - label_ids: список ID лейблов через запятую (если пусто, то все лейблы)
    """
    try:
        # Преобразование label_ids из строки в список
        labels_list = None
        if label_ids and label_ids.strip():
            try:
                labels_list = [int(lid.strip()) for lid in label_ids.split(",") if lid.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="label_ids должны быть числами через запятую")

        from celery import current_task
        task_id = current_task.request.id if current_task else None

        task_result = export_report_distribution_to_excel.delay(
            task_id, year, month_from, month_to, right_category_id, right_usage_type_id, labels_list
        )
        return {
            "message": "Задача экспорта распределённого отчёта запущена",
            "task_id": task_result.id,
            "description": "Результат будет экспортирован в файл report_distribution_<year>_<month_from>_<month_to>_<partner>_<category>_<usage_type>.xlsx",
            "params": {
                "year": year,
                "month_from": month_from,
                "month_to": month_to,
                "right_category_id": right_category_id,
                "right_usage_type_id": right_usage_type_id,
                "label_ids": labels_list if labels_list else "все лейблы"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запуске экспорта распределённого отчёта: {str(e)}")

STORAGE_DIR = "/app/storage"
@router.get("/download/{filename}")
async def download_file(filename: str):
    # Защита от path traversal – разрешаем только файлы из storage
    safe_path = os.path.join(STORAGE_DIR, os.path.basename(filename))
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(
        path=safe_path,
        filename=filename,
        media_type="application/octet-stream"
    )        

