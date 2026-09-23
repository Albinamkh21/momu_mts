import os
import uuid
from datetime import datetime

from services.catalog_diff_service import (
    get_catalog_diff, save_track_right_diff, update_staging_track_ids, save_track_contribution_diff,
    update_staging_track_ids, save_track_contribution_diff, save_track_right_diff, 
    get_catalog_diff, _sync_labels_v2, _sync_persons_v2, _insert_unique_persons_v2, 
    _sync_right_holders_v2, _sync_releases_v2, _sync_tracks_v2_isrc,
    _build_track_map_v2,_sync_track_releases_v2, _sync_track_contributions_v2, 
    _sync_track_labels_v2, _sync_right_holders_v2, _sync_track_rights_v2,
    _update_track_contributions_from_staging, _update_track_rights_from_staging,
    _sync_right_holders_v1, _sync_track_rights_v1,
    _sync_tracks_v2_label_code, _cleanup_staging_v2,
    get_processing_upload_id, update_upload_status, create_catalog_upload
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
def process_catalog_file_v2(self, file_path: str,  original_filename: str = "", label_id: int = None, user_id: int = None):
    task_id = self.request.id
    print(f"📂 Task process_catalog_file_v2[{self.request.id}] файл: {original_filename}")
    TaskProgress.emit(task_id, f"📂 Task process_catalog_file_v2[{self.request.id}] файл: {original_filename}")
    if not os.path.exists(file_path):
        return {"status": "error", "message": "File not found"}
    if label_id is None:
        return {"status": "error", "message": "Label ID is required"}

    upload_id = str(uuid.uuid4())
    start_time = datetime.now()    
    success = False
    try:
        with engine.begin() as conn:
            pass  # Можно добавить логику инициализации
            active_upload = get_processing_upload_id(conn, label_id)

            if active_upload:
                raise RuntimeError(
                    f"Для лейбла (ID: {label_id}) уже выполняется другая загрузка (upload_id: {active_upload})"
                )    

            create_catalog_upload(conn, upload_id, label_id, user_id, original_filename)
        
        df = pl.read_excel(file_path,infer_schema_length=0) 
        total_rows = len(df)
        chunk_size = 50000

        db_columns = [
            "track_id", "track_song_id",
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
            TaskProgress.emit(task_id, f"[v2] 📦 Загружен батч: {i} - {i + len(chunk)}")

        os.remove(file_path)
        success = True
        return {"status": "success", "total_rows": total_rows, "upload_id": upload_id}

    except Exception as e:
        print(f"[v2] ❌ Ошибка воркера: {str(e)}")
        TaskProgress.emit(task_id, f"[v2] ❌ Ошибка воркера: {str(e)}")
        raise e
        #return {"status": "error", "message": str(e)}
    finally:
        # Если произошла ошибка (success == False), очищаем staging для этого upload_id
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
            TaskProgress.emit(task_id, "🧹 Staging очищен после ошибки в process_catalog_file_v2")    


# ===========================================================================
#  TASK 2: Синхронизация справочников из staging_catalog_v2
# ===========================================================================

@celery_app.task(name="sync_catalog_dictionaries", bind=True)
def sync_catalog_dictionaries(self, prev_result, version="v2"):
    upload_id = prev_result.get("upload_id") if isinstance(prev_result, dict) else prev_result
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
            TaskProgress.emit(task_id, "📋 [v2] Начинаем синхронизацию справочников...")
            labels_count = _sync_labels_v2(conn, upload_id, staging_table=staging_table)
            persons_staging_count = _sync_persons_v2(conn, upload_id, staging_table=staging_table)

            # Phase 2: Нормализация (нужны закоммиченные данные)
            from .report_tasks import normalize_person_data, normalize_data
            print("📋 [v2] Нормализация staging_person...")
            TaskProgress.emit(task_id, "📋 [v2] Нормализация staging_person...")
            normalize_person_data("staging_person", "full_name", "tokens", "full_name_norm_key", connection=conn)
            print("📋 [v2] Нормализация staging_catalog_v2.track_name...")
            TaskProgress.emit(task_id, "📋 [v2] Нормализация staging_catalog_v2.track_name...")

            if version == "v2":
                normalize_data("staging_catalog_v2", "track_name", connection=conn)
            else:
                normalize_data("staging_catalog", "track_name", connection=conn)


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

            #_sync_track_labels_v2(conn, upload_id, staging_table=staging_table)

          
            

            #_cleanup_staging_v2(conn, upload_id, staging_table=staging_table)
            #print(f"🧹 Staging очищен после синхронизации.")
       
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
        with engine.begin() as conn:
           TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Начинаем обновление представлений.") 
           conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_extended; "))
           conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights_prev; "))
           conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights; "))
       
           print(f"🏁 Представления обновлены.")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Загружка каталога завершена полностью.")
    except Exception as e:
        print(f"[v2] ❌ Ошибка заполнения справочников: {e}")
        TaskProgress.emit(task_id, f"[v2] ❌ Ошибка заполнения справочников: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if not success:
            with engine.begin() as clean_conn:
                _cleanup_staging_v2(clean_conn, upload_id, staging_table=staging_table)
            TaskProgress.emit(task_id, "🧹 Staging очищен после ошибки")



@celery_app.task(name="tasks.generate_catalog_diff", bind=True)
def generate_catalog_diff_task(self, prev_result: dict, label_id: int) -> dict:
    """
    prev_result - это то, что вернула process_catalog_file_v2
    Например: {"status": "success", "upload_id": "1234-5678", "total_rows": 100}
    """
    
    # 1. Достаем upload_id из результата первой задачи
    upload_id = prev_result.get("upload_id")
    
    if not upload_id:
        return {"status": "error", "message": "upload_id не найден"}

    # 2. Вызываем саму логику расчета диффа
    with engine.begin() as conn:

        save_track_contribution_diff(conn, upload_id, task_id=getattr(self.request, 'id', None))
        save_track_right_diff(conn, upload_id, task_id=getattr(self.request, 'id', None))

        # 3. Собираем данные по изменившимся трекам (old/new) для проверки пользователем
        diff_rows = get_catalog_diff(conn, upload_id, label_id=label_id)

    return {
        "status": "completed",
        "upload_id": upload_id,
        "label_id": label_id,
        "total_diff_rows": len(diff_rows) // 2,
        "diff": diff_rows
    }


@celery_app.task(name="sync_catalog_dictionaries_for_update", bind=True)
def sync_catalog_dictionaries_for_update(self, prev_result, version="v2"):
    upload_id = prev_result.get("upload_id") if isinstance(prev_result, dict) else prev_result
    task_id = getattr(self.request, 'id', None)
    success = False
    staging_table = "staging_catalog_v2"
    try:
     
        # Phase 3: Основная синхронизация
        with engine.begin() as conn:
            print("📋 [v2] Начинаем синхронизацию справочников...")
            TaskProgress.emit(task_id, "📋 [v2] Начинаем синхронизацию справочников...")
            labels_count = _sync_labels_v2(conn, upload_id, staging_table=staging_table)
            persons_staging_count = _sync_persons_v2(conn, upload_id, staging_table=staging_table)

            # Phase 2: Нормализация 
            from .report_tasks import normalize_person_data, normalize_data
            print("📋 [v2] Нормализация staging_person...")
            TaskProgress.emit(task_id, "📋 [v2] Нормализация staging_person...")
            normalize_person_data("staging_person", "full_name", "tokens", "full_name_norm_key", connection=conn)
            print("📋 [v2] Нормализация staging_catalog_v2.track_name...")
            TaskProgress.emit(task_id, "📋 [v2] Нормализация staging_catalog_v2.track_name...")

            normalize_data("staging_catalog_v2", "track_name", connection=conn)

            persons_count = _insert_unique_persons_v2(conn, upload_id)
            #rights_count = _sync_right_holders_v2(conn, upload_id)
        
            releases_count = _sync_releases_v2(conn, upload_id, staging_table=staging_table)

            #Inportant diff between processing tracks
            # обновляет стеджинг, чтобы знать кто есть уже в таблице track
            update_staging_track_ids(conn, upload_id, task_id=getattr(self.request, 'id', None))



            
            # todo : нужно пометить треки, как новые или обновлённые, перед синхронизацией
            # в таблице track добавить флаг - 
            # или писать в staging_track_diff
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

            #_sync_track_labels_v2(conn, upload_id, staging_table=staging_table)

          
            

            #_cleanup_staging_v2(conn, upload_id, staging_table=staging_table)
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
        with engine.begin() as conn:
           TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Начинаем обновление представлений.") 
          #conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_extended; "))
           #conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights_prev; "))
           #conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights; "))
       
           print(f"🏁 Представления обновлены.")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Загружка каталога завершена полностью.")
    except Exception as e:
        print(f"[v2] ❌ Ошибка заполнения справочников: {e}")
        TaskProgress.emit(task_id, f"[v2] ❌ Ошибка заполнения справочников: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if not success:
            with engine.begin() as clean_conn:
                _cleanup_staging_v2(clean_conn, upload_id, staging_table=staging_table)
            TaskProgress.emit(task_id, "🧹 Staging очищен после ошибки")


@celery_app.task(name="sync_catalog_dictionaries_save_changes", bind=True)
def sync_catalog_dictionaries_save_changes(self, label_id):
    #upload_id = prev_result.get("upload_id") if isinstance(prev_result, dict) else prev_result
    upload_id = None
    task_id = getattr(self.request, 'id', None)
    success = False
    staging_table = "staging_catalog_v2"
    try:
     
        # Phase 3: Основная синхронизация
        with engine.begin() as conn:

            if label_id is not None:
                active_upload = get_processing_upload_id(conn, label_id)
                if active_upload:
                    upload_id = active_upload
            contributions_count = _update_track_contributions_from_staging(conn, upload_id)
            track_rights_count = _update_track_rights_from_staging(conn, upload_id)

            update_upload_status(conn, upload_id, "COMPLETED")
            #_cleanup_staging_v2(conn, upload_id, staging_table=staging_table)
            print(f"🧹 Staging очищен после синхронизации.")
       
            success = True

            return {
                "status": "success",
                "upload_id": upload_id,
                "stats": {
        
                    "track_contributions": contributions_count,
                    "track_rights": track_rights_count
                }
            }
        with engine.begin() as conn:
           TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Начинаем обновление представлений.") 
          #conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_extended; "))
           #conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights_prev; "))
           #conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights; "))
       
           print(f"🏁 Представления обновлены.")
        TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Загружка каталога завершена полностью.")
    except Exception as e:
        print(f"[v2] ❌ Ошибка заполнения справочников: {e}")
        TaskProgress.emit(task_id, f"[v2] ❌ Ошибка заполнения справочников: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        if not success:
            with engine.begin() as clean_conn:
                _cleanup_staging_v2(clean_conn, upload_id, staging_table=staging_table)
            TaskProgress.emit(task_id, "🧹 Staging очищен после ошибки")

@celery_app.task(name="tasks.get_catalog_diff_by_label_task", bind=True)
def get_catalog_diff_by_label_task(self,  label_id: int) -> dict:

    upload_id = None
    with engine.begin() as conn:

        diff_rows = get_catalog_diff(conn, upload_id, label_id=label_id)

    return {
        "status": "completed",
        "upload_id": upload_id,
        "label_id": label_id,
        "total_diff_rows": len(diff_rows) // 2,
        "diff": diff_rows
    }            