from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Optional
from copy import copy
from core.constants import RIGHT_HOLDER_TYPE
from docx import Document
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
import os
from core.config import get_project_root, settings

class DocumentService:
    BASE_STORAGE_DIR = settings.CONTRACTS_DIR

    # Лист шаблона contract_annex.xlsx с табличной частью (треки/авторы) и
    # номер первой строки этой таблицы (строка-образец, которую копируем для каждого элемента).
    ANNEX_ITEMS_SHEET = "Приложение 1-1"
    ANNEX_ITEMS_FIRST_ROW = 16
    ANNEX_ITEMS_COLUMNS = ("A", "B", "C", "D", "E", "F", "G", "H", "I")

    @staticmethod
    def _format_date_ru(d: Optional[date]) -> str:
        if not d:
            return ""
        return f"{d.day:02d}.{d.month:02d}.{d.year} г."

    @staticmethod
    def _format_date_kz(d: Optional[date]) -> str:
        if not d:
            return ""
        return f"{d.day:02d}.{d.month:02d}.{d.year} ж."

    @staticmethod
    def _format_date_plain(d: Optional[date]) -> str:
        """Дата без суффикса "г."/"ж." — для contract_annex.xlsx, где шаблон уже
        содержит эти суффиксы как текст сразу после тега."""
        if not d:
            return ""
        return f"{d.day:02d}.{d.month:02d}.{d.year}"

    @classmethod
    def _prepare_context(cls, contract, holder, payload_extra: dict) -> dict:
        """Отдельный метод для подготовки и маппинга контекста под теги шаблона."""
        contract_number = contract.contract_number
        holder_name = holder.name or holder.full_name or ""
        alias = holder.alias or ""
        signed_date = contract.signed_date or date.today()

        return {
            "num": contract_number,
            "doc_date": cls._format_date_ru(signed_date),
            "doc_date_kz": cls._format_date_kz(signed_date),
            "cname": holder_name,
            "cn_title": payload_extra.get("cn_title", "Гражданин(ка)"),
            
            # Маппинг реальных колонок RightHolder на теги шаблона:
            "iin": holder.iin_bin or "",
            "udl": holder.id_document_type or "Удостоверение личности",
            "udl_num_footer": holder.id_document_number or "",
            "udl_vidan": holder.id_document_issued_by or "",
            "udl_date": cls._format_date_ru(holder.id_document_issue_date),
            
            "artist_name": alias if alias else holder_name,
            "address": holder.address or "",
            "phone": holder.phone or "",
            "email": holder.email or "",
            
            # Банковские реквизиты:
            "bank_acc": holder.iban or "",
            "bank_name": holder.bank_name or "",
            "bank_bik": holder.bik or "",
            "bank_kbe": payload_extra.get("bank_kbe", ""),
            "director_short": payload_extra.get("director_short", holder_name),
        }

    @classmethod
    def _get_contract_dir(cls, contract, holder) -> Path:
        """Возвращает (и создает при необходимости) папку договора на диске.

        Используется и для договора, и для его приложений (annex), чтобы все
        сгенерированные документы одного договора лежали в одной папке.
        """
        contract_number = contract.contract_number
        holder_name = holder.name or holder.full_name or ""
        alias = holder.alias or ""

        safe_identifier = alias if alias else holder_name
        clean_folder_name = "".join(
            c for c in f"{contract_number}_{safe_identifier}" if c.isalnum() or c in (' ', '_', '-')
        ).strip()

        contract_dir = cls.BASE_STORAGE_DIR / clean_folder_name
        contract_dir.mkdir(parents=True, exist_ok=True)
        return contract_dir

    @classmethod
    def generate_contract_doc(cls, contract, holder, payload_extra: dict = None) -> str:
        payload_extra = payload_extra or {}
        
        contract_number = contract.contract_number
        
        # 1. Создание папки
        contract_dir = cls._get_contract_dir(contract, holder)

        client_type = payload_extra.get("type", RIGHT_HOLDER_TYPE.INDIVIDUAL)
        
        # 2. Получение пути к шаблону
        template_path = settings.CONTRACT_TEMPLATE_PATH
        if client_type == RIGHT_HOLDER_TYPE.COMPANY:
            template_path = settings.DOCS_DIR / "templates" / "contract_template_legal.docx"
        else:
             template_path = settings.DOCS_DIR / "templates" / "contract_template_phys.docx"
        

        # 3. Подготовка контекста через вынесенный метод
        context = cls._prepare_context(contract, holder, payload_extra)

        print(f"🛠️ [DEBUG] Ищу шаблон по пути: {template_path} | Существует: {template_path.exists()}", flush=True)
        # 4. Рендеринг и сохранение документа
        if template_path.exists():
            doc = Document(template_path)
            
            def replace_tags(element_container):
                for p in element_container.paragraphs:
                    for key, val in context.items():
                        target = f"${{{key}}}"
                        if target in p.text:
                            p.text = p.text.replace(target, str(val))

            replace_tags(doc)
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        replace_tags(cell)
        else:
            print(f"⚠️ [WARNING] Шаблон не найден! Создаю пустой документ.", flush=True)
            doc = Document()
            doc.add_heading(f"ЛИЦЕНЗИОННЫЙ ДОГОВОР № {contract_number}", level=1)
            for k, v in context.items():
                doc.add_paragraph(f"{k}: {v}")

        output_file_path = contract_dir / f"Договор_{contract_number}.docx"
        doc.save(output_file_path)
        
        print(f"📄 Файл договора создан: {output_file_path}", flush=True)
        return str(output_file_path)

    @classmethod
    def _prepare_annex_context(cls, contract, holder, annex) -> dict:
        """Контекст тегов ${...} для шаблона contract_annex.xlsx."""
        signed_date = contract.signed_date or date.today()
        holder_name = holder.name or holder.full_name or ""
        alias = holder.alias or ""

        return {
            "contract_num": contract.contract_number,
            "contract_date": cls._format_date_plain(signed_date),
            "contract_date_kz": cls._format_date_plain(signed_date),
            "pril_num": annex.annex_number,
            "doc_date": cls._format_date_plain(annex.doc_date),
            "doc_date_kz": cls._format_date_plain(annex.doc_date),
            "cname": holder_name,
            "iin": holder.iin_bin or "",
            "udl": holder.id_document_type or "Удостоверение личности",
            "artist_name": alias if alias else holder_name,
            "director_short": holder_name,
        }

    @staticmethod
    def _replace_placeholders_in_sheet(ws, context: dict) -> None:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and "${" in cell.value:
                    value = cell.value
                    for key, val in context.items():
                        value = value.replace(f"${{{key}}}", str(val))
                    cell.value = value

    @staticmethod
    def _insert_rows_preserving_merges(ws, idx: int, amount: int) -> None:
        """openpyxl.Worksheet.insert_rows сдвигает значения ячеек, но не диапазоны
        merged_cells под строкой вставки — их приходится пересчитывать вручную."""
        if amount <= 0:
            return
        to_shift = [rng for rng in list(ws.merged_cells.ranges) if rng.min_row >= idx]
        for rng in to_shift:
            ws.unmerge_cells(str(rng))

        ws.insert_rows(idx, amount=amount)

        for rng in to_shift:
            start = f"{get_column_letter(rng.min_col)}{rng.min_row + amount}"
            end = f"{get_column_letter(rng.max_col)}{rng.max_row + amount}"
            ws.merge_cells(f"{start}:{end}")

    @classmethod
    def _clone_row_style(cls, ws, src_row: int, dst_row: int) -> None:
        for col in cls.ANNEX_ITEMS_COLUMNS:
            src_cell = ws[f"{col}{src_row}"]
            dst_cell = ws[f"{col}{dst_row}"]
            dst_cell.font = copy(src_cell.font)
            dst_cell.fill = copy(src_cell.fill)
            dst_cell.border = copy(src_cell.border)
            dst_cell.alignment = copy(src_cell.alignment)
            dst_cell.number_format = src_cell.number_format

    @classmethod
    def _fill_annex_items(cls, ws, items) -> None:
        """Заполняет табличную часть приложения (треки/авторы), размножая строку-образец."""
        base_row = cls.ANNEX_ITEMS_FIRST_ROW
        extra_rows = max(len(items) - 1, 0)

        if extra_rows:
            cls._insert_rows_preserving_merges(ws, base_row + 1, extra_rows)
            for i in range(extra_rows):
                cls._clone_row_style(ws, base_row, base_row + 1 + i)

        for idx, item in enumerate(items):
            row = base_row + idx
            ws[f"A{row}"] = item.line_number
            ws[f"B{row}"] = item.code or ""
            ws[f"C{row}"] = item.track_title
            ws[f"D{row}"] = item.artist_name
            ws[f"E{row}"] = float(item.related_rights_percent)
            ws[f"F{row}"] = item.composer_name
            ws[f"G{row}"] = float(item.composer_percent)
            ws[f"H{row}"] = item.lyricist_name
            ws[f"I{row}"] = float(item.lyricist_percent)

    @classmethod
    def generate_annex_doc(cls, contract, holder, annex) -> str:
        """Генерирует .xlsx приложения к договору (contract_annex.xlsx) и сохраняет
        его в папку договора. Возвращает путь к сгенерированному файлу."""
        contract_dir = cls._get_contract_dir(contract, holder)

        template_path = settings.DOCS_DIR / "templates" / "contract_annex.xlsx"
        if not template_path.exists():
            raise FileNotFoundError(f"Шаблон приложения не найден: {template_path}")

        wb = load_workbook(template_path)
        context = cls._prepare_annex_context(contract, holder, annex)

        for ws in wb.worksheets:
            cls._replace_placeholders_in_sheet(ws, context)

        items_ws = wb[cls.ANNEX_ITEMS_SHEET]
        cls._fill_annex_items(items_ws, annex.items)

        safe_annex_number = "".join(
            c for c in annex.annex_number if c.isalnum() or c in ('-', '_')
        ).strip() or str(annex.id)

        output_file_path = contract_dir / f"Приложение_{safe_annex_number}.xlsx"
        wb.save(output_file_path)

        print(f"📄 Файл приложения создан: {output_file_path}", flush=True)
        return str(output_file_path)