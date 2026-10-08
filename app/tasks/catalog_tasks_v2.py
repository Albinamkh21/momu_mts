import os
import uuid
from datetime import datetime
from services.catalog_diff_service import (
    _build_track_map_v2, _cleanup_staging_v2, _insert_unique_persons_v2, _sync_labels_v2, _sync_persons_v2,
    _sync_releases_v2, _sync_right_holders_v1, _sync_right_holders_v2, _sync_track_contributions_v2, _sync_track_labels_v2,
    _sync_track_releases_v2, _sync_track_rights_v1, _sync_track_rights_v2, _sync_tracks_v2_isrc, _sync_tracks_v2_label_code, _update_release_info_from_staging,
    _update_track_contributions_from_staging, _update_track_rights_from_staging, _update_tracks_common_info_from_staging, create_catalog_upload, find_release_diff, find_track_contribution_diff,
    find_track_right_diff, find_tracks_common_info_diff, get_catalog_diff, get_processing_upload_id, refresh_track_materialized_views, update_catalog_deleted_tracks, update_staging_track_ids,
      update_upload_status, update_catalog_statistics, get_catalog_deleted_tracks
)

import polars as pl
from polars import lit
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.celery_app import celery_app
from .utils import clean_null_bytes
from celery import current_task
from services.broadcaster import TaskProgress


import sys

def get_database_url():
    # Проверяем не только env-переменные, но и запущен ли сейчас pytest в принципе.
    # Если запущен pytest, но DATABASE_URL_TEST почему-то пустой, 
    # мы можем программно подставить тестовую базу или принудительно ругаться.
    is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "true"
    
    if is_testing:
        test_url = os.getenv("DATABASE_URL_TEST")
        if test_url:
            return test_url
        # Если тест идет, а тестовой переменной нет — подставляем тестовую базу явно по шаблону
        return os.getenv("DATABASE_URL", "").replace("/momu", "/momu_test")
        
    return os.getenv("DATABASE_URL")

DATABASE_URL = get_database_url()
engine = create_engine(DATABASE_URL)

# ===========================================================================
#  TASK 1: Загрузка файла в staging_catalog_v2
# ===========================================================================

@celery_app.task(name="process_catalog_file_v2", bind=True)
def process_catalog_file_v2(self, file_path: str, upload_id: str, original_filename: str = "", label_id: int = None, user_id: int = None, is_additional_data: bool = True):
    task_id = self.request.id
    print(f" 🚀 -------------------------- ЗАПУСК  ЗАГРУЗКИ КАТАЛОГА ------------------------------")
    print(f"1️⃣ Task process_catalog_file_v2[{self.request.id}] файл: {original_filename}")
    TaskProgress.emit(upload_id, f"📂 Task process_catalog_file_v2[{self.request.id}] файл: {original_filename}")
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File not found"}
    if label_id is None:
        return {"status": "error", "message": "Label ID is required"}

    
    start_time = datetime.now()    
    success = False
    try:
        with engine.begin() as conn:
            pass  # Можно добавить логику инициализации
            active_upload = get_processing_upload_id(conn, label_id)

            if active_upload:
                if is_additional_data:
                   
                    print(f"Для лейбла (ID: {label_id}) выполняется дополнительная загрузка к сессии {active_upload}")
                    upload_id = active_upload 
                else:
               
                    raise RuntimeError(
                        f"Для лейбла (ID: {label_id}) уже выполняется другая загрузка (upload_id: {active_upload}). "
                        "Дождитесь окончания или отметьте 'Дополнительная загрузка'."
                    )
            else:
              create_catalog_upload(conn, upload_id, label_id, user_id, original_filename)

        
        df = pl.read_excel(file_path,infer_schema_length=0) 
        total_rows = len(df)
        chunk_size = 50000

        db_columns = [
            "upc", "isrc", "track_name", "genre_name", "album_name",
            "album_single", "track_number", "artist_name", "track_artist_name",
            "composer", "lyricist", "authors", "explicit", "duration",
            "label_name", "right_id",
            "author_right_int", "author_right_mob", "author_right_pub", "ar_label_treaty_number",
            "related_right_id_int", "related_right_id_mob", "related_right_id_pub", "rr_label_treaty_number",
            "types_of_rights", "countries", "create_date", "release_date",
            "sales_start_date", "has_ringtone", "ringtone_upc", "ringtone_isrc",
            "has_vclip", "vclip_isrc", "video_upc", "has_lyrics", "has_ttml",
            "effective_date", "termination_date", "active_inactive", "resource_reference"
        ]

        for i in range(0, total_rows, chunk_size):
            chunk = df.slice(i, chunk_size)
            chunk.columns = db_columns
            chunk = clean_null_bytes(chunk)

            # Обрабатываем поле isrc - берём только первую часть до точки с запятой
            chunk = chunk.with_columns(
                pl.col("isrc")
                .str.split(";")
                .list.first()
                .str.strip_chars()
                .alias("isrc")
            )

            chunk = chunk.with_columns(
                pl.col("explicit")
                .str.to_lowercase()
                .str.strip_chars()
                .is_in(["true", "yes", "1", "explicit", "да"])
                .cast(pl.String)
                .alias("explicit")
            )
            
            chunk = chunk.with_columns(
                pl.col("release_date")
                .str.strip_chars()
                .str.extract(r"^(\d{4}-\d{2}-\d{2})", 1)
                .str.to_date("%Y-%m-%d", strict=False)
                .dt.to_string("%Y-%m-%d")
                .alias("release_date")
            )

        

            chunk = chunk.with_columns([
                pl.lit(upload_id).alias("upload_id"),
                pl.lit(user_id).alias("user_id"), 
                pl.lit(start_time).alias("created_at")
            ])
            chunk.write_database(
                table_name="staging_catalog_v2",
                connection=DATABASE_URL,
                if_table_exists="append",
                engine="adbc"
            )
            print(f"[v2] 📦 Загружен батч: {i} - {i + len(chunk)}")
            TaskProgress.emit(upload_id, f"[v2] 📦 Загружен батч: {i} - {i + len(chunk)}")

        os.remove(file_path)
        success = True
        return {"status": "success", "total_rows": total_rows, "upload_id": upload_id}

    except Exception as e:
        print(f"[v2] ❌ Ошибка воркера: {str(e)}")
        TaskProgress.emit(upload_id, f"[v2] ❌ Ошибка воркера: {str(e)}")
        raise e
        #return {"status": "error", "message": str(e)}
    finally:
      
        if not success:
            with engine.begin() as clean_conn:
                clean_conn.execute(
                    text("DELETE FROM staging_catalog_v2 WHERE upload_id = :uid"),
                    {"uid": upload_id}
                )
                clean_conn.execute(
                    text("DELETE FROM staging_person WHERE upload_id = :uid"),
                    {"uid": upload_id}
                )
                clean_conn.execute(
                text("DELETE FROM catalog_upload WHERE upload_id = :uid"),
                {"uid": upload_id}
            )
            TaskProgress.emit(upload_id, "🧹 Staging очищен после ошибки в process_catalog_file_v2")    


# ===========================================================================
#  TASK 2: Синхронизация справочников из staging_catalog_v2
# ===========================================================================

@celery_app.task(name="sync_catalog_dictionaries", bind=True)
def sync_catalog_dictionaries(self, prev_result, version="v2", upload_id: str = None):
    upload_id = upload_id or (prev_result.get("upload_id") if isinstance(prev_result, dict) else prev_result)
    task_id = getattr(self.request, 'id', None)
    success = False
    if version == "v2":
        staging_table = "staging_catalog_v2"
    else:    
        staging_table = "staging_catalog"
    try:
     
        # Phase 3: Основная синхронизация
        with engine.begin() as conn:
            print("📋 [v2] Начинаем синхронизацию справочников...")
            TaskProgress.emit(upload_id, "📋 [v2] Начинаем синхронизацию справочников...")
            labels_count = _sync_labels_v2(conn, upload_id, staging_table=staging_table)
            persons_staging_count = _sync_persons_v2(conn, upload_id, staging_table=staging_table)

            # Phase 2: Нормализация (нужны закоммиченные данные)
            from .report_tasks import normalize_person_data, normalize_data
            print("📋 [v2] Нормализация staging_person...")
            TaskProgress.emit(upload_id, "📋 [v2] Нормализация staging_person...")
            normalize_person_data("staging_person", "full_name", "tokens", "full_name_norm_key", connection=conn)
           
           
            print("📋 [v2] Нормализация staging_catalog_v2.track_name...")
            TaskProgress.emit(upload_id, "📋 [v2] Нормализация staging_catalog_v2.track_name...")
            normalize_data("staging_catalog_v2", "track_name", connection=conn)
       
            print("📋 [v2] Нормализация staging_catalog_v2.album_name...")
            TaskProgress.emit(upload_id, "📋 [v2] Нормализация staging_catalog_v2.album_name...")
            normalize_data("staging_catalog_v2", "album_name", connection=conn)
                


            persons_count = _insert_unique_persons_v2(conn, upload_id)
            #rights_count = _sync_right_holders_v2(conn, upload_id)
        
            releases_count = _sync_releases_v2(conn, upload_id, staging_table=staging_table)
            
            tracks_count_isrc = _sync_tracks_v2_isrc(conn, upload_id, staging_table=staging_table)   
            tracks_count_code = _sync_tracks_v2_label_code(conn, upload_id, staging_table=staging_table)
           

            _build_track_map_v2(conn, upload_id, staging_table=staging_table)

            track_release_count = _sync_track_releases_v2(conn, upload_id, staging_table=staging_table)
            contributions_count = _sync_track_contributions_v2(conn, upload_id)

            #track_rights_count = _sync_track_rights_v2(conn, upload_id)
            _sync_track_labels_v2(conn, upload_id, staging_table=staging_table)

            if version == "v2":
                rights_count = _sync_right_holders_v2(conn, upload_id, staging_table=staging_table)
                track_rights_count = _sync_track_rights_v2(conn, upload_id, staging_table=staging_table)
            else:
                rights_count = _sync_right_holders_v1(conn, upload_id)
                track_rights_count = _sync_track_rights_v1(conn, upload_id)

            

          
            

            _cleanup_staging_v2(conn, upload_id, staging_table=staging_table)
            print(f"🧹 Staging очищен после синхронизации.")
       
            success = True

            return {
                "status": "success",
                "upload_id": upload_id,
                "stats": {
                    "labels": labels_count,
                    "persons_staging": persons_staging_count,
                    "persons": persons_count,
                    "right_holders": rights_count,
                    "releases": releases_count,
                    "tracks": tracks_count_isrc + tracks_count_code,
                    "track_releases": track_release_count,
                    "track_contributions": contributions_count,
                    "track_rights": track_rights_count
                }
            }
        #refresh_track_materialized_views(conn)
    except Exception as e:
        print(f"[v2] ❌ Ошибка заполнения справочников: {e}")
        TaskProgress.emit(upload_id, f"[v2] ❌ Ошибка заполнения справочников: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if not success:
            with engine.begin() as clean_conn:
                _cleanup_staging_v2(clean_conn, upload_id, staging_table=staging_table)
            TaskProgress.emit(upload_id, "🧹 Staging очищен после ошибки")



@celery_app.task(name="tasks.find_catalog_diff", bind=True)
def find_catalog_diff_task(self,prev_result, label_id: int, upload_id: str = None) -> dict:
 
    
    print(f"-- 3️⃣.  find_catalog_diff_task started for upload_id: {upload_id}")
    TaskProgress.emit(upload_id, f"-- 3️⃣  find_catalog_diff_task upload_id: {upload_id}")
    
    if not upload_id:
        return {"status": "error", "message": "upload_id не найден"}

   
    with engine.begin() as conn:

        find_track_contribution_diff(conn, upload_id,  label_id=label_id, task_id=getattr(self.request, 'id', None))
        find_track_right_diff(conn, upload_id,  label_id=label_id, task_id=getattr(self.request, 'id', None))
        find_tracks_common_info_diff(conn, upload_id, label_id=label_id, task_id=getattr(self.request, 'id', None))
        find_release_diff(conn, upload_id, task_id=getattr(self.request, 'id', None))  

        # 3. Собираем данные по изменившимся трекам (old/new) для проверки пользователем
        diff_rows = get_catalog_diff(conn, upload_id, label_id=label_id)
        result_stats = update_catalog_statistics(conn, upload_id, task_id=getattr(self.request, 'id', None))

    return {
        "status": "completed",
        "upload_id": upload_id,
        "label_id": label_id,
        "total_diff_rows": len(diff_rows) // 2,
        "diff": diff_rows,
        "stats": result_stats
    }


@celery_app.task(name="update_catalog_step_1_prepare_data", bind=True)
def update_catalog_step_1_prepare_data(self, prev_result, version="v2", upload_id=None):
    upload_id = upload_id or (prev_result.get("upload_id") if isinstance(prev_result, dict) else prev_result)
    print(f"2️⃣   Starting update_catalog_step_1_prepare_data for upload_id: {upload_id}")
    TaskProgress.emit(upload_id, f"Starting update_catalog_step_1_prepare_data for upload_id: {upload_id}")
    task_id = getattr(self.request, 'id', None)
    success = False
    staging_table = "staging_catalog_v2"
    try:
        with engine.begin() as conn:
            print("📋 [v2] Начинаем синхронизацию справочников...")
            TaskProgress.emit(upload_id, "📋 [v2] Начинаем синхронизацию справочников...")
            labels_count = _sync_labels_v2(conn, upload_id, staging_table=staging_table)
            persons_staging_count = _sync_persons_v2(conn, upload_id, staging_table=staging_table)

          
            from .report_tasks import normalize_person_data, normalize_data
            print("📋 [v2] Нормализация staging_person...")
            TaskProgress.emit(upload_id, "📋 [v2] Нормализация staging_person...")
            normalize_person_data("staging_person", "full_name", "tokens", "full_name_norm_key", connection=conn)

            print("📋 [v2] Нормализация staging_catalog_v2.track_name...")
            TaskProgress.emit(upload_id, "📋 [v2] Нормализация staging_catalog_v2.track_name...")
            normalize_data("staging_catalog_v2", "track_name", connection=conn)
                 
            print("📋 [v2] Нормализация staging_catalog_v2.album_name...")
            TaskProgress.emit(upload_id, "📋 [v2] Нормализация staging_catalog_v2.album_name...")
            normalize_data("staging_catalog_v2", "album_name", connection=conn)
                
            #print("📋 [v2] Нормализация release.title...")
            #TaskProgress.emit(upload_id, "📋 [v2] Нормализация release.title...")
            #normalize_data(table_name="release", column_name="title", connection=conn)
            
        
            update_staging_track_ids(conn, upload_id, task_id=getattr(self.request, 'id', None))



            
            success = True

            return {
                "status": "success",
                "upload_id": upload_id,
                "stats": {
                    "labels": labels_count,
                    "persons_staging": persons_staging_count,
        
                }
            }
          
    except Exception as e:
        print(f"[v2] ❌ Ошибка заполнения справочников  step 1: {e}")
        TaskProgress.emit(upload_id, f"[v2] ❌ Ошибка заполнения справочников step 1: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if not success:
            with engine.begin() as clean_conn:
                _cleanup_staging_v2(clean_conn, upload_id, staging_table=staging_table)
            TaskProgress.emit(upload_id, "🧹 Staging очищен после ошибки")





@celery_app.task(name="update_catalog_step_2_new_tracks", bind=True)
def update_catalog_step_2_new_tracks(self, label_id=None):
    upload_id = None
    task_id = getattr(self.request, 'id', None)
    success = False
    staging_table = "staging_catalog_v2"
    try:
     
        with engine.begin() as conn:
            if label_id is not None:
                active_upload = get_processing_upload_id(conn, label_id)
                if active_upload:
                    upload_id = active_upload
            print("📋 Начинаем загрузку новых треков в справочники.." , upload_id)
            TaskProgress.emit(upload_id, f"🚀 Начинаем загрузку новых треков в справочники...")
                       
            persons_count = _insert_unique_persons_v2(conn, upload_id)
            releases_count = _sync_releases_v2(conn, upload_id, staging_table=staging_table)

            
            #new tracks
            tracks_count_isrc = _sync_tracks_v2_isrc(conn, upload_id, staging_table=staging_table)   
            tracks_count_code = _sync_tracks_v2_label_code(conn, upload_id, staging_table=staging_table)
           

            _build_track_map_v2(conn, upload_id, staging_table=staging_table)

            track_release_count = _sync_track_releases_v2(conn, upload_id, staging_table=staging_table)
            contributions_count = _sync_track_contributions_v2(conn, upload_id)

    
            _sync_track_labels_v2(conn, upload_id, staging_table=staging_table)

          
            rights_count = _sync_right_holders_v2(conn, upload_id, staging_table=staging_table)
            track_rights_count = _sync_track_rights_v2(conn, upload_id, staging_table=staging_table)
        

            #_sync_track_labels_v2(conn, upload_id, staging_table=staging_table)

          
            

            #_cleanup_staging_v2(conn, upload_id, staging_table=staging_table)
            print(f"🧹 Staging очищен после синхронизации.")
       
            success = True

            return {
                "status": "success",
                "upload_id": upload_id,
                "stats": {
                    "persons": persons_count,
                    "right_holders": rights_count,
                    "releases": releases_count,
                    "tracks": tracks_count_isrc + tracks_count_code,
                    "track_releases": track_release_count,
                    "track_contributions": contributions_count,
                    "track_rights": track_rights_count
                }
            }
            #refresh_track_materialized_views(conn) 
    except Exception as e:
        print(f"[v2] ❌ Ошибка заполнения справочников: {e}")
        TaskProgress.emit(upload_id, f"[v2] ❌ Ошибка заполнения справочников: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if not success:
            with engine.begin() as clean_conn:
                _cleanup_staging_v2(clean_conn, upload_id, staging_table=staging_table)
            TaskProgress.emit(upload_id, "🧹 Staging очищен после ошибки")

@celery_app.task(name="update_catalog_save_changes", bind=True)
def update_catalog_save_changes(self, prev_result, label_id):
    upload_id = prev_result.get("upload_id") if isinstance(prev_result, dict) else prev_result
    #upload_id = None
    task_id = getattr(self.request, 'id', None)
    success = False
    staging_table = "staging_catalog_v2"
    try:

        with engine.begin() as conn:
            if label_id is not None and upload_id is None:
                active_upload = get_processing_upload_id(conn, label_id)
                if active_upload:
                    upload_id = active_upload
            contributions_count = _update_track_contributions_from_staging(conn, upload_id)
            track_rights_count = _update_track_rights_from_staging(conn, upload_id, label_id)
            track_common_info_count = _update_tracks_common_info_from_staging(conn, upload_id)
            release_info_count = _update_release_info_from_staging(conn, upload_id)

            #deleted_tracks_count = update_catalog_deleted_tracks(conn, label_id, upload_id)
            #print(f"Deleted tracks count: {deleted_tracks_count}")
            #TaskProgress.emit(upload_id, f"Deleted tracks count: {deleted_tracks_count}")

            update_upload_status(conn, upload_id, "COMPLETED")
            _cleanup_staging_v2(conn, upload_id, staging_table=staging_table)
            print(f"🧹 Staging очищен после синхронизации.")
       
            success = True

            return {
                "status": "success",
                "upload_id": upload_id,
                "stats": {
        
                    "track_contributions": contributions_count,
                    "track_rights": track_rights_count,
                    "track_common_info": track_common_info_count
                }
            }
            #refresh_track_materialized_views(conn)
    except Exception as e:
        print(f"[v2] ❌ Ошибка заполнения справочников: {e}")
        TaskProgress.emit(upload_id, f"[v2] ❌ Ошибка заполнения справочников: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if not success:
            with engine.begin() as clean_conn:
                _cleanup_staging_v2(clean_conn, upload_id, staging_table=staging_table)
            TaskProgress.emit(upload_id, "🧹 Staging очищен после ошибки")

@celery_app.task(name="tasks.get_catalog_diff_by_label_task", bind=True)
def get_catalog_diff_by_label_task(self,  label_id: int) -> dict:

    upload_id = None
    task_id = getattr(self.request, 'id', None)
    with engine.begin() as conn:

        diff_rows = get_catalog_diff(conn, upload_id, label_id=label_id)
        
        # Получаем активную загрузку для этого лейбла и подсчитываем статистику
        if not upload_id:
            active_upload = get_processing_upload_id(conn, label_id)
            if active_upload:
                upload_id = active_upload
        
        result_stats = {}
        if upload_id:
            result_stats = update_catalog_statistics(conn, upload_id, task_id=task_id)

    return {
        "status": "completed",
        "upload_id": upload_id,
        "label_id": label_id,
        "total_diff_rows": len(diff_rows) // 2,
        "diff": diff_rows,
        "stats": result_stats
    }   



@celery_app.task(name="update_catalog_delete_changes", bind=True)
def update_catalog_delete_changes(self, label_id):

    upload_id = None
    task_id = getattr(self.request, 'id', None)
    success = False
    staging_table = "staging_catalog_v2"
    try:
        with engine.begin() as conn:

            if label_id is not None:
                active_upload = get_processing_upload_id(conn, label_id)
                if active_upload:
                    upload_id = active_upload
          
            # Получаем статистику перед удалением
            result_stats = {}
            if upload_id:
                result_stats = update_catalog_statistics(conn, upload_id, task_id=task_id)
            
            update_upload_status(conn, upload_id, "DELETED")
            _cleanup_staging_v2(conn, upload_id, staging_table=staging_table)
            print(f"🧹 Staging очищен после синхронизации.")
       
            success = True
            return {
                "status": "success",
                "upload_id": upload_id,
                "stats": result_stats
            }
        #refresh_track_materialized_views(conn)
        TaskProgress.emit(upload_id, f"✅ Удаление предварительных данных каталога завершена полностью.")
    except Exception as e:
        print(f"[v2] ❌ Ошибка заполнения справочников: {e}")
        TaskProgress.emit(upload_id, f"[v2] ❌ Ошибка заполнения справочников: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if not success:
            with engine.begin() as clean_conn:
                _cleanup_staging_v2(clean_conn, upload_id, staging_table=staging_table)
            TaskProgress.emit(upload_id, "🧹 Staging очищен после ошибки")

@celery_app.task(name="get_catalog_deleted_task", bind=True)
def get_catalog_deleted_task(self, label_id):
    task_id = getattr(self.request, 'id', None)
    with engine.begin() as conn:
        upload_id = None
        if label_id is not None:
            active_upload = get_processing_upload_id(conn, label_id)
            if active_upload:
                upload_id = active_upload
            else:
                raise RuntimeError(
                    f"Для лейбла (ID: {label_id}) нет активной загрузки "
                   
                )    

        deleted_tracks = get_catalog_deleted_tracks(conn, label_id, upload_id=upload_id)
    return {
            "diff": deleted_tracks,
            "total_diff_rows": len(deleted_tracks)
        }

@celery_app.task(name="update_views_task", bind=True)
def update_views_task(self, label_id):
    task_id = getattr(self.request, 'id', None)
    with engine.begin() as conn:
        # Здесь должна быть логика обновления представлений для указанного label_id
        refresh_track_materialized_views(conn)
    return {"status": "success", "message": f"Представления  обновлены."}