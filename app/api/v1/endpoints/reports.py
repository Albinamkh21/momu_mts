from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os
from uuid import uuid4
from celery import chain
from tasks.report_tasks import process_report_file, update_catalog_dictionaries_from_report, insert_data_into_final_report_table, group_report_data

router = APIRouter()

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
            process_report_file.s(file_path), 
            update_catalog_dictionaries_from_report.si()
            #insert_data_into_final_report_table.si(1, 1, 1, 1, 2026)  # partner_id, right_category_id, right_usage_type_id, month, year
        )
 
    task_result = workflow.apply_async()
    #task_result = process_report_file.delay(file_path)



    return {
        "message": "Файл отчёта принят и поставлен в очередь на обработку",
        "task_id": task_result.id,
        "filename": file.filename
    }


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

