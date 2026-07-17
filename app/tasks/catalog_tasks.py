import os
import re as _re
import uuid
from datetime import datetime
import time
import polars as pl
from polars import lit
from sqlalchemy import create_engine, text
from core.celery_app import celery_app
from celery import current_task
from .utils import clean_null_bytes
from core.constants import RightCategory, RightUsageType

from services.broadcaster import TaskProgress
from services.csv_writer import BaseCSVWriter, TomeExcelWriter, TomeWriterFactory
import xlsxwriter
import csv



DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)






def build_standard_query(fields_base: str, group_by: str, extra_where: str = "",
                          label_id: int = None, right_usage_type_id: int = None) -> tuple:
    """Генератор для стандартных плоских запросов (separate_by_rights).
    Работает с track_right, где каждый тип использования - отдельная строка, поэтому
    колонки-пивот (CASE WHEN) и фильтр по right_usage_type_id формируются здесь же.
    fields_base должен содержать плейсхолдер '{columns_sql}' на месте пивот-колонок.
    """
    types_to_process = [
        (RightUsageType.INT, "INT"),
        (RightUsageType.MOB, "MOB"),
        (RightUsageType.PUB, "PUB"),
    ]
    if right_usage_type_id and right_usage_type_id != RightUsageType.ALL:
        if right_usage_type_id == RightUsageType.INT:
            types_to_process = [(RightUsageType.INT, "INT")]
        elif right_usage_type_id == RightUsageType.MOB:
            types_to_process = [(RightUsageType.MOB, "MOB")]
        elif right_usage_type_id == RightUsageType.PUB:
            types_to_process = [(RightUsageType.PUB, "PUB")]

    case_sql = ", ".join([
        f"MAX(CASE WHEN tr.right_usage_type_id = {rut_id} THEN tr.share_percentage ELSE 0 END) AS {label}"
        for rut_id, label in types_to_process
    ])

    where_parts, params = [], {}
    if label_id:
        where_parts.append("m.label_id = :label_id")
        params["label_id"] = label_id
    if right_usage_type_id and right_usage_type_id != RightUsageType.ALL:
        where_parts.append("(tr.right_usage_type_id = :rut_id and share_percentage > 0)")
        params["rut_id"] = right_usage_type_id
    if extra_where:
        where_parts.append(extra_where)

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
        SELECT {fields_base.replace('{columns_sql}', case_sql)}
        FROM 
        mv_track_extended m
        JOIN track_right tr ON tr.track_id = m.track_id
        JOIN right_holder rh ON rh.id = tr.right_holder_id
        JOIN label l ON l.id = rh.label_id
        {where_clause}
        {group_by} 
        ORDER BY m.label_id, m.track_id;
    """
    return query, params

def build_unified_rights_query_old(where_clause: str, right_usage_type_id: int = None) -> str:
    if right_usage_type_id and right_usage_type_id != RightUsageType.ALL:
        suffix = right_usage_type_id.name.lower()
        rel_sql = f"COALESCE(ra.rel_{suffix}, 0) AS related_{suffix}"
        auth_sql = f"COALESCE(ra.auth_{suffix}, 0) AS author_{suffix}"
        filter_sql = f"ra.rel_{suffix} >= 100 AND ra.auth_{suffix} >= 100"
    else:
        rel_sql = "COALESCE(ra.rel_int, 0) AS rel_int, COALESCE(ra.rel_mob, 0) AS rel_mob, COALESCE(ra.rel_pub, 0) AS rel_pub"
        auth_sql = "COALESCE(ra.auth_int, 0) AS auth_int, COALESCE(ra.auth_mob, 0) AS auth_mob, COALESCE(ra.auth_pub, 0) AS auth_pub"
        filter_sql = "(ra.rel_int + ra.rel_mob + ra.rel_pub) >= 300 AND (ra.auth_int + ra.auth_mob + ra.auth_pub) >= 300"

    # Добавляем фильтрацию прав прямо в текущий WHERE
    if where_clause and "WHERE" in where_clause.upper():
        final_where = f"{where_clause} AND {filter_sql}"
    elif where_clause:
        final_where = f"WHERE {where_clause} AND {filter_sql}"
    else:
        final_where = f"WHERE {filter_sql}"

    return f"""
        SELECT 
            m.label_own_code,
            m.upc, m.isrc, m.track_name, m.artist_name,
            m.authors, m.composer, m.lyricist, m.album_name,
            {rel_sql},
            ra.rel_holders AS copyright_holder_related,
            ra.base_code,
            {auth_sql},
            ra.auth_holders AS copyright_holder_author,
            TO_CHAR(m.created_at::timestamp, 'DD-MM-YYYY') AS "Time period"
        FROM mv_track_extended m
        JOIN mv_track_rights ra ON ra.track_id = m.track_id
        {final_where}
        ORDER BY m.label_id, ra.base_code;
    """  
def build_unified_rights_query(label_id: int = None, right_usage_type_id: int = None,
                                is_100plus: bool = True, extra_where: str = "") -> tuple:
    """Генератор для унифицированных запросов (default, 100plus100).
    Работает с mv_track_rights, где каждый тип использования - уже отдельная КОЛОНКА
    (rel_int/rel_mob/rel_pub, auth_int/auth_mob/auth_pub), а не строка, как в track_right.
    Поэтому фильтр по right_usage_type_id здесь не нужен/невозможен - вместо этого
    выбираются нужные колонки, а фильтрация 100+ идёт по их значениям.
    """
    if right_usage_type_id and right_usage_type_id != RightUsageType.ALL:
        if right_usage_type_id == RightUsageType.INT:
            suffix = "int"
        elif right_usage_type_id == RightUsageType.MOB:
            suffix = "mob"
        elif right_usage_type_id == RightUsageType.PUB:
            suffix = "pub"

        rel_sql = f"COALESCE(tr.rel_{suffix}, 0) AS related_{suffix}"
        auth_sql = f"COALESCE(tr.auth_{suffix}, 0) AS author_{suffix}"
        # Фильтр применяется только если is_100plus=True
        filter_sql = f"tr.rel_{suffix} >= 100 AND tr.auth_{suffix} >= 100" if is_100plus else ""
    else:
        rel_sql = "COALESCE(tr.rel_int, 0) AS rel_int, COALESCE(tr.rel_mob, 0) AS rel_mob, COALESCE(tr.rel_pub, 0) AS rel_pub"
        auth_sql = "COALESCE(tr.auth_int, 0) AS auth_int, COALESCE(tr.auth_mob, 0) AS auth_mob, COALESCE(tr.auth_pub, 0) AS auth_pub"
        # Фильтр применяется только если is_100plus=True
        filter_sql = "(tr.rel_int + tr.rel_mob + tr.rel_pub) >= 300 AND (tr.auth_int + tr.auth_mob + tr.auth_pub) >= 300" if is_100plus else ""

    where_parts, params = [], {}
    if label_id:
        where_parts.append("m.label_id = :label_id")
        params["label_id"] = label_id
    if filter_sql:
        where_parts.append(filter_sql)
    if extra_where:
        where_parts.append(extra_where)

    final_where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
        SELECT 
            m.label_own_code,
            m.upc, m.isrc, m.track_name, m.artist_name,
            m.authors, m.composer, m.lyricist, m.album_name,
            {rel_sql},
            tr.rel_holders AS copyright_holder_related,
            tr.base_code,
            {auth_sql},
            tr.auth_holders AS copyright_holder_author,
            TO_CHAR(m.created_at::timestamp, 'DD-MM-YYYY') AS "Time period"
        FROM mv_track_extended m
        JOIN mv_track_rights tr ON tr.track_id = m.track_id
        {final_where}
        ORDER BY m.label_id, tr.base_code;
    """
    return query, params
@celery_app.task(name="export_normalized_catalog_to_flat", bind=True)
def export_normalized_catalog_to_flat(self, output_path: str = None, label_id: int = None, right_usage_type_id: int = None, export_format: str = "default"):
    task_id = self.request.id

    if not export_format:
        export_format = "default"
    if not right_usage_type_id:
        right_usage_type_id = RightUsageType.ALL
    TaskProgress.emit(task_id, f"✅ Начало выгрузки ({export_format}).")
    print(f"✅ Начало выгрузки ({export_format}) - right_usage_type_id {right_usage_type_id}; label_id: {label_id}")

    # Списки колонок для separate_by_rights. Плейсхолдер {columns_sql} заменяется на CASE WHEN
    # пивот-колонки внутри build_standard_query (только там нужен пивот, т.к. только там строки track_right).
    # Форматы default/100plus100 используют build_unified_rights_query, которая сама формирует
    # свои колонки из mv_track_rights (там типы использования - уже колонки, а не строки).
    fields_related = """  m.label_own_code , m.upc, m.isrc, m.track_name, m.artist_name,  m.authors, m.composer, m.lyricist, m.album_name,
           {columns_sql},
            l.name AS copyright_holder """

    fields_author = """ m.track_id, m.label_own_code, m.track_name, m.artist_name,  m.authors, m.composer, m.lyricist, 
           {columns_sql},
            l.name AS copyright_holder """

    fields_factory = {
        "separate_by_rights": {
            "_author": fields_author,
            "_related": fields_related
        }
    }

    group_clause = {
        "separate_by_rights": " GROUP BY  m.track_id, m.label_own_code, m.upc, m.isrc, m.track_name, m.artist_name,  m.authors, m.composer, m.lyricist, m.album_name, l.name, m.label_id ",
    }

    # Конфигурация проходов и суффиксов для полей
    if export_format == "separate_by_rights":
        passes = [
            {"suffix": "_author", "field_key": "_author", "cat_id": RightCategory.AUTHOR, "msg": "авторские"},
            {"suffix": "_related", "field_key": "_related", "cat_id": RightCategory.RELATED, "msg": "смежные"}
        ]
    else:
        passes = [{"suffix": "", "field_key": "default", "cat_id": None, "msg": "все"}]

    storage_dir = output_path or "/app/storage"
    os.makedirs(storage_dir, exist_ok=True)
    total_rows = 0
    CHUNK_SIZE = 100000


    # 3. Выполнение и запись
    try:
        with engine.connect() as conn:
            for p in passes:
                # Дополнительный фильтр по категории прав (только для раздельного прохода separate_by_rights)
                extra_where = ""
                extra_params = {}
                if p["cat_id"] is not None:
                    TaskProgress.emit(task_id, f"⏳ Запуск прохода: {p['msg']} права...")
                    extra_where = "(tr.right_category_id = :cat_id and share_percentage > 0)"
                    extra_params["cat_id"] = p["cat_id"]

                # Формирование колонок и фильтров по label_id/right_usage_type_id инкапсулировано
                # в build_standard_query/build_unified_rights_query - у них разные исходные таблицы
                # (track_right - строки на тип использования, mv_track_rights - уже колонки).
                if export_format == "default":
                    # Для default используем единый запрос без фильтра 100%
                    query, params = build_unified_rights_query(
                        label_id=label_id, right_usage_type_id=right_usage_type_id,
                        is_100plus=False, extra_where=extra_where
                    )

                elif export_format == "100plus100":
                    # Для 100plus100 используем тот же запрос, но с фильтром 100%
                    query, params = build_unified_rights_query(
                        label_id=label_id, right_usage_type_id=right_usage_type_id,
                        is_100plus=True, extra_where=extra_where
                    )

                elif export_format == "separate_by_rights":
                    # Для раздельных файлов оставляем классический плоский запрос с группировкой
                    current_fields = fields_factory["separate_by_rights"][p["field_key"]]
                    query, params = build_standard_query(
                        current_fields, group_clause["separate_by_rights"], extra_where=extra_where,
                        label_id=label_id, right_usage_type_id=right_usage_type_id
                    )

                params.update(extra_params)

                base_filename = f"catalog_{export_format}_{p['suffix']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                # Выполнение запроса
                result = conn.execution_options(stream_results=True).execute(text(query), params)
                TaskProgress.emit(task_id, f"✅ Запрос выполнен для прохода: {p['msg']} права. Начинаем выгрузку в файл...")
                print(f"✅ Запрос выполнен для прохода: {p['msg']} права. Начинаем выгрузку в файл...")

                headers = result.keys()

                #full_writer = BaseCSVWriter(os.path.join(storage_dir, f"{base_filename}_full.csv"), headers)
                tome_writer = TomeWriterFactory.create("xlsx", base_filename, storage_dir, headers, max_rows=CHUNK_SIZE * 5)
                 


                while True:
                    chunk = result.fetchmany(CHUNK_SIZE)
                    if not chunk: 
                        break
                    
                    #full_writer.write_rows(chunk)
                    tome_writer.write_rows(chunk)
                    
                    total_rows += len(chunk)
                    if total_rows % 50000 == 0:
                        TaskProgress.emit(task_id, f"⏳ Выгружено {total_rows} строк...")

                #full_writer.close()
                tome_writer.close()

        if total_rows == 0:
            return {"status": "success", "message": "Нет данных"}

        TaskProgress.emit(task_id, f"✅ Успешно: {total_rows} строк.")
        return {"status": "success", "rows_exported": total_rows}

    except Exception as e:
        TaskProgress.emit(task_id, f"❌ Ошибка: {e}", level="error")
        return {"status": "error", "message": str(e)}






@celery_app.task(name="delete_data_from_all_dictionaries_by_label", bind=True)
def delete_data_from_all_dictionaries_by_label(self, label_id: int):
    """
    Удаляет все данные о треках, связях и правах, привязанных к указанному лейблу.
    Базовые справочники (label,  right_category,
    right_usage_type, finding_source, partners, contract) остаются нетронутыми.
    """
    try:
        task_id = self.request.id
        with engine.begin() as conn:
            # 1. Находим все track_id, привязанные к лейблу
            track_ids_result = conn.execute(text("""
                SELECT track_id FROM track_label WHERE label_id = :label_id
            """), {"label_id": label_id})
            track_ids = [row[0] for row in track_ids_result.fetchall()]

            if not track_ids:
                TaskProgress.emit(task_id, f"🗑️ Нет треков для данного лейбла")
                return {"status": "success", "label_id": label_id, "message": "Нет треков для данного лейбла", "deleted": {}}
  

            print(f"🗑️ Найдено треков для удаления: {len(track_ids)}")
            TaskProgress.emit(task_id, f"🗑️ Найдено треков для удаления: {len(track_ids)}")


            # 6. Удаляем track_label (все связи этих треков, не только текущий лейбл)
            r_track_label = conn.execute(text("""
                DELETE FROM track_label WHERE track_id = ANY(:ids)  and label_id = :label_id
            """), {"ids": track_ids, "label_id": label_id})
            print(f"✅ track_label удалено: {r_track_label.rowcount}")
            TaskProgress.emit(task_id, f"✅ track_label удалено: {r_track_label.rowcount}")

            
            # 3. Определяем, какие треки остались без лейблов (осиротели)
            remaining_tracks = conn.execute(text("""
                SELECT DISTINCT track_id FROM track_label WHERE track_id = ANY(:ids)
            """), {"ids": track_ids}).fetchall()
            remaining_track_ids = {row[0] for row in remaining_tracks}

            orphan_track_ids = [tid for tid in track_ids if tid not in remaining_track_ids]
            TaskProgress.emit(task_id, f"✅ Найдено осиротевших треков: {len(orphan_track_ids)}")


            # 2. Удаляем report (нет ON DELETE CASCADE)
            r_report = conn.execute(text("""
                DELETE FROM report_track_rights_cache WHERE track_id = ANY(:ids)
            """), {"ids": orphan_track_ids})
            print(f"✅ report удалено: {r_report.rowcount}")
            TaskProgress.emit(task_id, f"✅ report удалено: {r_report.rowcount}")

            # 3. Удаляем track_right
            r_track_right = conn.execute(text("""
                DELETE FROM track_right WHERE track_id = ANY(:ids) and right_holder_id IN (select id from right_holder where label_id = :label_id)
                
            """), {"ids": orphan_track_ids, "label_id": label_id})
            print(f"✅ track_right удалено: {r_track_right.rowcount}")
            TaskProgress.emit(task_id, f"✅ track_right удалено: {r_track_right.rowcount}")

            # 4. Удаляем track_contribution
            r_track_contribution = conn.execute(text("""
                DELETE FROM track_contribution WHERE track_id = ANY(:ids) 
            """), {"ids": orphan_track_ids})
            print(f"✅ track_contribution удалено: {r_track_contribution.rowcount}")
            TaskProgress.emit(task_id, f"✅ track_contribution удалено: {r_track_contribution.rowcount}")

            # 5. Удаляем track_release
            r_track_release = conn.execute(text("""
                DELETE FROM track_release WHERE track_id = ANY(:ids)
            """), {"ids": orphan_track_ids})
            print(f"✅ track_release удалено: {r_track_release.rowcount}")
            TaskProgress.emit(task_id, f"✅ track_release удалено: {r_track_release.rowcount}")

        

            # 7. Удаляем сами треки
            r_tracks = conn.execute(text("""
                DELETE FROM track WHERE id = ANY(:ids)
            """), {"ids": orphan_track_ids})
            print(f"✅ track удалено: {r_tracks.rowcount}")
            TaskProgress.emit(task_id, f"✅ track удалено: {r_tracks.rowcount}")

            # 8. Удаляем осиротевшие релизы (без треков)
            r_releases = conn.execute(text("""
                DELETE FROM release r
                WHERE r.label_id = :label_id
                AND NOT EXISTS (
                    SELECT 1 FROM track_release tr WHERE tr.release_id = r.id
                )
            """), {"label_id": label_id})
            print(f"✅ release (осиротевших) удалено: {r_releases.rowcount}")
            TaskProgress.emit(task_id, f"✅ release (осиротевших) удалено: {r_releases.rowcount}")

            # 9. Удаляем осиротевших артистов (у которых больше нет контрибьюций)
            r_persons = conn.execute(text("""
                DELETE FROM person p
                WHERE NOT EXISTS (
                    SELECT 1 FROM track_contribution tc WHERE tc.person_id = p.id 
                )
            """))
            print(f"✅ person (осиротевших) удалено: {r_persons.rowcount}")
            TaskProgress.emit(task_id, f"✅ person (осиротевших) удалено: {r_persons.rowcount}")

            r_right_holders = conn.execute(text("""
                DELETE FROM right_holder rh
                WHERE NOT EXISTS (SELECT 1 FROM track_right tr WHERE tr.right_holder_id = rh.id)
            """))
            print(f"✅ right_holder (осиротевших) удалено: {r_right_holders.rowcount}")
            TaskProgress.emit(task_id, f"✅ right_holder (осиротевших) удалено: {r_right_holders.rowcount}")

            stats = {
                "tracks": r_tracks.rowcount,
                "reports": r_report.rowcount,
                "track_rights": r_track_right.rowcount,
                "track_contributions": r_track_contribution.rowcount,
                "track_releases": r_track_release.rowcount,
                "track_labels": r_track_label.rowcount,
                "releases": r_releases.rowcount,
                "persons": r_persons.rowcount

            }

        with engine.begin() as conn:
            #обновляем материализованное представление, чтобы не было рассинхрона
           TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Начинаем обновление представлений.") 
           conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_extended; "))
           conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights_prev; "))
           conn.execute(text("REFRESH MATERIALIZED VIEW  mv_track_rights; "))
           print(f"🏁 Представления обновлены.")
           TaskProgress.emit(getattr(current_task.request, 'id', None), f"✅ Представления обновлены.")


        print(f"🏁 Удаление по лейблу {label_id} завершено: {stats}")
        TaskProgress.emit(task_id, f"🏁 Удаление по лейблу {label_id} завершено: {stats}")
        return {"status": "success", "label_id": label_id, "deleted": stats}

    except Exception as e:
        print(f"❌ Ошибка удаления по лейблу: {e}")
        TaskProgress.emit(task_id, f"❌ Ошибка удаления по лейблу: {e}")
        return {"status": "error", "message": str(e)}


