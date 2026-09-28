from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import shutil
import os
from uuid import uuid4
from celery import chain
from celery.result import AsyncResult
from core.celery_app import celery_app
from tasks.catalog_tasks_v2 import find_catalog_diff_task, get_catalog_diff_by_label_task, process_catalog_file_v2, sync_catalog_dictionaries, update_catalog_delete_changes,  update_catalog_save_changes, update_catalog_step_1_prepare_data, update_catalog_step_2_new_tracks
from api.deps import get_current_user, User, Depends

router = APIRouter()

STORAGE_DIR = "/app/storage"

@router.post("/upload_v2")
async def upload_catalog_v2(file: UploadFile = File(...), label_id: int = Form(...), current_user: User = Depends(get_current_user)):
    if not file.filename.endswith(('.xlsx', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_id = str(uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(STORAGE_DIR, f"{file_id}{file_ext}")

    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

  
    workflow = chain(
        process_catalog_file_v2.s(file_path, original_filename=file.filename, label_id=label_id, user_id=current_user.id),
        sync_catalog_dictionaries.s("v2"),
    )

    task_result = workflow.apply_async()

    return {
        "message": "Файл принят и поставлен в очередь на обработку (v2)",
        "task_id": task_result.id,
        "filename": file.filename
    }




@router.post("/recalculate_diff")
async def recalculate_diff(file: UploadFile = File(...), 
                           label_id: int = Form(...), 
                           is_additional_data: bool = Form(True),
                           current_user: User = Depends(get_current_user)):
    if not file.filename.endswith(('.xlsx')):
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_id = str(uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(STORAGE_DIR, f"{file_id}{file_ext}")

    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    workflow = chain(
       
        process_catalog_file_v2.s(file_path, original_filename=file.filename, label_id=label_id, user_id=current_user.id, is_additional_data=is_additional_data), 
        update_catalog_step_1_prepare_data.s("v2"),
        find_catalog_diff_task.s(label_id=label_id)
      
    )

    task_result = workflow.apply_async()

    return {
        "message": "Файл принят и поставлен в очередь на перерасчёт diff",
        "task_id": task_result.id,
        "filename": file.filename
      
    }


@router.get("/diff_result/{task_id}")
async def get_diff_result(task_id: str):
    """Опрос результата цепочки recalculate_diff по task_id последней задачи (find_catalog_diff_task)."""
    task_result = AsyncResult(task_id, app=celery_app)

    if not task_result.ready():
        return {"status": task_result.state, "ready": False}

    if task_result.failed():
        return {"status": "FAILURE", "ready": True, "error": str(task_result.result)}

    return {"status": "SUCCESS", "ready": True, "result": task_result.result}


@router.post("/save_catalog_diff")
async def save_catalog_diff(label_id: int = Form(...)):
   
    workflow = chain(

        update_catalog_step_2_new_tracks.s(label_id=label_id),
        update_catalog_save_changes.s(label_id=label_id)
    )

    task_result = workflow.apply_async()


    return {
        "message": "Запущена задача изменения каталога",
        "task_id": task_result.id,
        "filename": None
    }

@router.post("/delete_catalog_diff")
async def delete_catalog_diff(label_id: int = Form(...)):
   
    workflow = chain(
        update_catalog_delete_changes.s(label_id=label_id)
    )

    task_result = workflow.apply_async()


    return {
        "message": "Запущена задача удаления изменений ",
        "task_id": task_result.id,
        "filename": None
    }

@router.get("/get_catalog_diff/{label_id}")
async def get_catalog_diff(label_id: int):
   
    workflow = chain(
        get_catalog_diff_by_label_task.s(label_id)
    )

    task_result = workflow.apply_async()


    return {
        "message": "Запущена задача получения изменений ",
        "task_id": task_result.id,
        "filename": None
    }



@router.get("/download_catalog_diff/{label_id}")
async def download_catalog_diff(label_id: int):
   
    workflow = chain(
        get_catalog_diff_by_label_task.s(label_id)
    )

    task_result = workflow.apply_async()


    return {
        "message": "Запущена задача скачивания diff ",
        "task_id": task_result.id,
        "filename": None
    }


@router.get("/get_catalog_deleted/{label_id}")
async def get_catalog_deleted(label_id: int):
   
    workflow = chain(
        get_catalog_diff_by_label_task.s(label_id)
    )

    task_result = workflow.apply_async()


    return {
        "message": "Запущена задача получения удалённых записей ",
        "task_id": task_result.id,
        "filename": None
    }