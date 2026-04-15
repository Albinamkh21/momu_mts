from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
import shutil
import os
from uuid import uuid4
from celery import chain
from tasks.report_tasks import (
    process_report_file, update_catalog_dictionaries_from_report,
    insert_data_into_final_report_table, group_report_data, find_lost_track,
    process_full_report_pipeline, normalize_person_data, normalize_staging_report_agg, normalize_data
)

router = APIRouter()


class ReportDataRequest(BaseModel):
    partner_id: int
    right_category_id: int
    right_usage_type_id: int
    month: int = Field(..., ge=1, le=12)
    year: int

STORAGE_DIR = "/app/storage"

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
    3. Обновление словарей каталога (update_catalog_dictionaries_from_report)
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
