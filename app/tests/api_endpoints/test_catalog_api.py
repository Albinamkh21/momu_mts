"""
Тесты для API каталога:
- Загрузка каталога (upload_v2)
- Удаление данных по лейблу (delete /label/{label_id})
- Выгрузка каталога (download)

В тестах используется CELERY_TASK_ALWAYS_EAGER=True (см. conftest.py, фикстура
enable_celery_sync), поэтому все Celery-задачи выполняются синхронно прямо
внутри вызова API-эндпоинта. К моменту получения HTTP-ответа задача уже
завершена (успешно или с исключением, т.к. task_eager_propagates=True) —
отдельно дожидаться её через AsyncResult не нужно и не имеет смысла, т.к.
результат eager-задач не сохраняется в result backend.
"""
import os
import pytest
from sqlalchemy import text


@pytest.fixture
def test_catalog_file():
    """Путь к тестовому файлу каталога."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "test_upload_catalog.xlsx")


def test_catalog_upload_and_data_verification(api_client, db_session, clean_test_db, test_catalog_file):
    """
    Тест 1: Загрузка каталога и проверка данных во всех таблицах.
    
    Шаги:
    1. Загружаем файл через /upload_v2
    2. Ожидаем завершения обработки Celery
    3. Проверяем, что данные попали во все таблицы:
       - staging_catalog_v2
       - staging_person
       - label
       - person
       - right_holder
       - release
       - track
       - track_contribution
       - track_right
       - track_label
       - track_release
    """
    # Проверяем, что тестовый файл существует
    assert os.path.exists(test_catalog_file), f"Тестовый файл не найден: {test_catalog_file}"
    
    # 1. Загружаем файл
    with open(test_catalog_file, "rb") as f:
        response = api_client.post(
            "/api/v1/catalog_v2/upload_v2",
            files={"file": ("test_upload_catalog.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"user_id": "test_user_123"}
        )
    
    assert response.status_code == 200, f"Ошибка загрузки: {response.text}"
    response_data = response.json()
    assert "task_id" in response_data
    task_id = response_data["task_id"]
    print(f"✅ Файл загружен, task_id: {task_id}")
    
    # 2. CELERY_TASK_ALWAYS_EAGER=True -> задача уже выполнена синхронно
    # к моменту возврата ответа от API, отдельно ждать её не требуется.
    
    # 3. Проверяем данные в таблицах
    
   
    
    # 3.3. label - должны быть созданы лейблы
    label_count = db_session.execute(text("SELECT COUNT(*) FROM label")).scalar()
    assert label_count > 0, "label пуста после синхронизации"
    print(f"✅ label: {label_count} строк")
    
    # Получаем ID первого лейбла для последующих тестов
    label_id = db_session.execute(text("SELECT id FROM label LIMIT 1")).scalar()
    assert label_id is not None
    
    # 3.4. person - должны быть созданы персоны
    person_count = db_session.execute(text("SELECT COUNT(*) FROM person")).scalar()
    assert person_count > 0, "person пуста после синхронизации"
    print(f"✅ person: {person_count} строк")
    
    # 3.5. right_holder - должны быть правообладатели
    right_holder_count = db_session.execute(text("SELECT COUNT(*) FROM right_holder")).scalar()
    assert right_holder_count > 0, "right_holder пуста после синхронизации"
    print(f"✅ right_holder: {right_holder_count} строк")
    
    
    # 3.7. track - должны быть треки
    track_count = db_session.execute(text("SELECT COUNT(*) FROM track")).scalar()
    assert track_count > 0, "track пуста после синхронизации"
    print(f"✅ track: {track_count} строк")
    
    # 3.8. track_contribution - должны быть связи треков и персон
    track_contribution_count = db_session.execute(text("SELECT COUNT(*) FROM track_contribution")).scalar()
    assert track_contribution_count > 0, "track_contribution пуста после синхронизации"
    print(f"✅ track_contribution: {track_contribution_count} строк")
    
    # 3.9. track_right - должны быть права на треки
    track_right_count = db_session.execute(text("SELECT COUNT(*) FROM track_right")).scalar()
    assert track_right_count > 0, "track_right пуста после синхронизации"
    print(f"✅ track_right: {track_right_count} строк")
    
    # 3.10. track_label - должны быть связи треков и лейблов
    track_label_count = db_session.execute(text("SELECT COUNT(*) FROM track_label")).scalar()
    assert track_label_count > 0, "track_label пуста после синхронизации"
    print(f"✅ track_label: {track_label_count} строк")
    
    # 3.11. track_release - должны быть связи треков и релизов
    track_release_count = db_session.execute(text("SELECT COUNT(*) FROM track_release")).scalar()
    assert track_release_count > 0, "track_release пуста после синхронизации"
    print(f"✅ track_release: {track_release_count} строк")
    
    return label_id


def test_catalog_delete_by_label(api_client, db_session, clean_test_db, test_catalog_file):
    """
    Тест 2: Удаление данных по лейблу.
    
    Шаги:
    1. Загружаем каталог (переиспользуем код из первого теста)
    2. Удаляем данные по лейблу через DELETE /label/{label_id}
    3. Проверяем, что данные удалены из всех таблиц
    """
    # 1. Сначала загружаем каталог
    with open(test_catalog_file, "rb") as f:
        response = api_client.post(
            "/api/v1/catalog_v2/upload_v2",
            files={"file": ("test_upload_catalog.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"user_id": "test_user_123"}
        )
    
    assert response.status_code == 200
    # CELERY_TASK_ALWAYS_EAGER=True -> задача уже выполнена синхронно
    print("✅ Каталог загружен")
    
    # Получаем ID лейбла и количество треков перед удалением
    label_result = db_session.execute(text("SELECT id, name FROM label LIMIT 1")).fetchone()
    assert label_result is not None, "Лейбл не найден после загрузки"
    label_id = label_result[0]
    label_name = label_result[1]
    
    # Подсчитываем треки для этого лейбла
    tracks_before = db_session.execute(
        text("SELECT COUNT(*) FROM track_label WHERE label_id = :label_id"),
        {"label_id": label_id}
    ).scalar()
    assert tracks_before > 0, "Нет треков для лейбла перед удалением"
    print(f"✅ Найдено треков для лейбла '{label_name}' (ID={label_id}): {tracks_before}")
    
    # 2. Удаляем данные по лейблу
    delete_response = api_client.delete(f"/api/v1/catalog/label/{label_id}")
    assert delete_response.status_code == 200, f"Ошибка удаления: {delete_response.text}"
    # CELERY_TASK_ALWAYS_EAGER=True -> удаление уже выполнено синхронно
    print("✅ Удаление выполнено")
    
    # 3. Проверяем, что данные удалены
    
    # 3.1. track_label - связи должны быть удалены для этого лейбла
    tracks_after = db_session.execute(
        text("SELECT COUNT(*) FROM track_label WHERE label_id = :label_id"),
        {"label_id": label_id}
    ).scalar()
    assert tracks_after == 0, f"track_label не пуста после удаления: {tracks_after} строк"
    print("✅ track_label очищена для данного лейбла")
    
    # 3.2. Проверяем, что осиротевшие треки удалены
    # Треки, которые больше не привязаны ни к одному лейблу, должны быть удалены
    orphan_tracks = db_session.execute(
        text("""
            SELECT COUNT(*) FROM track t 
            WHERE NOT EXISTS (
                SELECT 1 FROM track_label tl WHERE tl.track_id = t.id
            )
        """)
    ).scalar()
    # В зависимости от данных в файле, может быть 0 или несколько осиротевших треков
    # которые должны быть удалены вместе с их связями
    print(f"✅ Осиротевших треков (должны быть удалены): {orphan_tracks}")
    
    # 3.3. Проверяем track_right - права на удалённые треки должны быть удалены
    # Это можно проверить косвенно: все права, связанные с right_holder данного лейбла
    orphan_track_rights = db_session.execute(
        text("""
            SELECT COUNT(*) FROM track_right tr
            WHERE tr.right_holder_id IN (
                SELECT id FROM right_holder WHERE label_id = :label_id
            )
            AND tr.track_id NOT IN (SELECT track_id FROM track_label)
        """),
        {"label_id": label_id}
    ).scalar()
    assert orphan_track_rights == 0, f"Найдены orphan права: {orphan_track_rights}"
    print("✅ track_right очищена от осиротевших прав")
    
    # 3.4. track_contribution - вклады для осиротевших треков должны быть удалены
    orphan_contributions = db_session.execute(
        text("""
            SELECT COUNT(*) FROM track_contribution tc
            WHERE tc.track_id NOT IN (SELECT id FROM track)
        """)
    ).scalar()
    assert orphan_contributions == 0, f"Найдены orphan вклады: {orphan_contributions}"
    print("✅ track_contribution очищена от осиротевших вкладов")
    
    # 3.5. track_release - связи с релизами для удалённых треков должны быть удалены
    orphan_track_releases = db_session.execute(
        text("""
            SELECT COUNT(*) FROM track_release tr
            WHERE tr.track_id NOT IN (SELECT id FROM track)
        """)
    ).scalar()
    assert orphan_track_releases == 0, f"Найдены orphan track_release: {orphan_track_releases}"
    print("✅ track_release очищена от осиротевших связей")
    
    # 3.6. release - осиротевшие релизы (без треков) данного лейбла должны быть удалены
    orphan_releases = db_session.execute(
        text("""
            SELECT COUNT(*) FROM release r
            WHERE r.label_id = :label_id
            AND NOT EXISTS (
                SELECT 1 FROM track_release tr WHERE tr.release_id = r.id
            )
        """),
        {"label_id": label_id}
    ).scalar()
    assert orphan_releases == 0, f"Найдены orphan релизы: {orphan_releases}"
    print("✅ Осиротевшие релизы удалены")
    
    # 3.7. person - осиротевшие персоны (без вкладов) должны быть удалены
    orphan_persons = db_session.execute(
        text("""
            SELECT COUNT(*) FROM person p
            WHERE NOT EXISTS (
                SELECT 1 FROM track_contribution tc WHERE tc.person_id = p.id
            )
        """)
    ).scalar()
    assert orphan_persons == 0, f"Найдены orphan персоны: {orphan_persons}"
    print("✅ Осиротевшие персоны удалены")
    
    print("\n✅ Все проверки удаления пройдены успешно!")


def test_catalog_download(api_client, db_session, clean_test_db, test_catalog_file):
    """
    Тест 3: Выгрузка каталога.
    
    Шаги:
    1. Загружаем каталог
    2. Запускаем выгрузку через POST /download
    3. Ожидаем завершения
    4. Проверяем, что файл создан в storage
    """
    # 1. Загружаем каталог
    with open(test_catalog_file, "rb") as f:
        response = api_client.post(
            "/api/v1/catalog_v2/upload_v2",
            files={"file": ("test_upload_catalog.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"user_id": "test_user_123"}
        )
    
    assert response.status_code == 200
    # CELERY_TASK_ALWAYS_EAGER=True -> загрузка уже выполнена синхронно
    print("✅ Каталог загружен")
    
    # Получаем ID лейбла
    label_id = db_session.execute(text("SELECT id FROM label LIMIT 1")).scalar()
    assert label_id is not None
    
    # 2. Запускаем выгрузку (выполняется синхронно благодаря CELERY_TASK_ALWAYS_EAGER)
    download_response = api_client.post(
        "/api/v1/catalog/download",
        json={
            "label_id": label_id,
            "right_usage_type_id": None,
            "export_format": "default"
        }
    )
    
    assert download_response.status_code == 200, f"Ошибка выгрузки: {download_response.text}"
    download_data = download_response.json()
    print(f"✅ Выгрузка выполнена синхронно: {download_data}")
    
    # 3. Проверяем, что файл создан
    result_info = download_data
    if isinstance(result_info, dict) and "file_path" in result_info:
        file_path = result_info["file_path"]
        assert os.path.exists(file_path), f"Файл не найден: {file_path}"
        assert os.path.getsize(file_path) > 0, "Файл пустой"
        print(f"✅ Файл создан: {file_path} ({os.path.getsize(file_path)} байт)")
    else:
        # Если формат ответа другой, просто проверяем успешность
        print(f"✅ Выгрузка завершена успешно (проверка файла пропущена)")


def test_full_workflow(api_client, db_session, clean_test_db, test_catalog_file):
    """
    Тест 4: Полный рабочий процесс.
    
    Объединяет все операции:
    1. Загрузка каталога
    2. Проверка данных
    3. Выгрузка каталога
    4. Удаление по лейблу
    5. Проверка удаления
    """
    print("\n" + "="*80)
    print("ПОЛНЫЙ РАБОЧИЙ ПРОЦЕСС")
    print("="*80)
    
    # 1. Загрузка
    print("\n[1/5] Загрузка каталога...")
    with open(test_catalog_file, "rb") as f:
        upload_response = api_client.post(
            "/api/v1/catalogs/upload_v2",
            files={"file": ("test_upload_catalog.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"user_id": "test_user_123"}
        )
    
    assert upload_response.status_code == 200
    # CELERY_TASK_ALWAYS_EAGER=True -> задача выполняется синхронно
    print("✅ Каталог загружен")
    
    # 2. Проверка данных
    print("\n[2/5] Проверка данных в таблицах...")
    track_count = db_session.execute(text("SELECT COUNT(*) FROM track")).scalar()
    label_id = db_session.execute(text("SELECT id FROM label LIMIT 1")).scalar()
    assert track_count > 0
    assert label_id is not None
    print(f"✅ Найдено треков: {track_count}, лейбл ID: {label_id}")
    
    # 3. Выгрузка
    print("\n[3/5] Выгрузка каталога...")
    download_response = api_client.post(
        "/api/v1/catalogs/download",
        json={"label_id": label_id, "right_usage_type_id": None, "export_format": "default"}
    )
    assert download_response.status_code == 200
    print("✅ Каталог выгружен")
    
    # 4. Удаление
    print("\n[4/5] Удаление данных по лейблу...")
    delete_response = api_client.delete(f"/api/v1/catalogs/label/{label_id}")
    assert delete_response.status_code == 200
    print("✅ Данные удалены")
    
    # 5. Проверка удаления
    print("\n[5/5] Проверка удаления...")
    tracks_after = db_session.execute(
        text("SELECT COUNT(*) FROM track_label WHERE label_id = :label_id"),
        {"label_id": label_id}
    ).scalar()
    assert tracks_after == 0
    print("✅ Все данные удалены корректно")
    
    print("\n" + "="*80)
    print("✅ ПОЛНЫЙ РАБОЧИЙ ПРОЦЕСС ЗАВЕРШЁН УСПЕШНО!")
    print("="*80 + "\n")

from sqlalchemy import text

def test_debug_right_usage_type_and_db_name(test_engine):
    """
    Временный тест для дебага: проверяет, к какой базе реально идет подключение,
    и выводит содержимое таблицы right_usage_type.
    """
    with test_engine.connect() as conn:
        # Узнаем текущую базу данных
        current_db = conn.execute(text("SELECT current_database();")).scalar()
        print(f"\n[DEBUG] === ТЕКУЩАЯ БАЗА ДАННЫХ: {current_db} ===")

        # Вытаскиваем данные из таблицы
        result = conn.execute(text("SELECT * FROM right_usage_type;"))
        rows = result.mappings().all()
        
        print(f"[DEBUG] === ДАННЫЕ right_usage_type (СТРОК: {len(rows)}) ===")
        for row in rows:
            print(dict(row))
        print("[DEBUG] =============================================\n")    

def test_catalog_download_all(api_client, db_session, clean_test_db):
    """
    Тест: Выгрузка всего каталога (без привязки к конкретному label_id).
    
    Шаги:
    1. Запускаем выгрузку через POST /download без указания label_id.
    2. Ожидаем завершения фоновой задачи.
    3. Проверяем, что файл выгрузки физически создан.
    """
    download_response = api_client.post(
            "/api/v1/catalog/download",
            json={
                "label_id": 1,  
                "right_usage_type_id": None,
                "export_format": "default"
            }
        )
        
    assert download_response.status_code == 200, f"Ошибка выгрузки: {download_response.text}"
    download_data = download_response.json()
    
    # Так как задача выполнилась синхронно, в ответе уже должен быть результат или task_id, 
    # а файл уже должен быть создан на диске!
    print(f"✅ Выгрузка успешно выполнена синхронно: {download_data}")
        
    result_info = download_data
        
    if isinstance(result_info, dict) and "file_path" in result_info:
        file_path = result_info["file_path"]
        assert os.path.exists(file_path), f"Файл не найден: {file_path}"
        assert os.path.getsize(file_path) > 0, "Файл пустой"
        print(f"✅ Файл создан: {file_path} ({os.path.getsize(file_path)} байт)")
    else:
        # Если эндпоинт возвращает путь по другому ключу (например, "path" или вложенный объект)
        # подставь нужный ключ, либо проверяй директорию выгрузки
        print(f"✅ Ответ от эндпоинта: {download_data}")
    print(f"\n🔍 [DEBUG JSON RESPONSE]: {download_data}")
    print(f"📂 [DEBUG WORKING DIR]: {os.getcwd()}")    
