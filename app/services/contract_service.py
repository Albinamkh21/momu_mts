"""ContractService — business logic for the Contract module."""
from __future__ import annotations

import os
import platform
import subprocess
from asyncio.log import logger
from pathlib import Path
from typing import Optional

import re
import uuid
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from __schemas.external_contract import ExternalContractCreateRequest
from .document_service import DocumentService   

from __crud.contract_repository import ContractNumberConflictError, ContractRepository
from __crud.right_holder_repository import RightHolderRepository
from __schemas.contracts import ContractCreate, ContractResponse, ContractUpdate
from core.constants import _TRANSLIT_MAP
from difflib import SequenceMatcher
from datetime import datetime
from services.csv_writer import TomeWriterFactory


class ContractService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ContractRepository(db)
        self.right_holder_repo = RightHolderRepository(db)
       

    @staticmethod
    def _to_response(obj) -> ContractResponse:
        return ContractResponse(
            id=obj.id,
            rights_holder_id=obj.right_holder_id,
            right_holder_name=obj.right_holder.name if obj.right_holder else None,
            contract_number=obj.contract_number,
            signed_date=obj.signed_date,
            valid_from=obj.valid_from,
            valid_to=obj.valid_to,
            status=obj.status,
            direction_type=obj.direction_type,
            file_path=obj.file_path,
            file_name=obj.file_name,
        )

    def list(
        self,
        *,
        right_holder_id: Optional[int] = None,
        status_: Optional[str] = None,
        direction_type: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContractResponse], int]:
        items, total = self.repo.get_all(
            right_holder_id=right_holder_id,
            status=status_,
            direction_type=direction_type,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )
        return [self._to_response(item) for item in items], total

    def get(self, contract_id: int) -> ContractResponse:
        obj = self.repo.get_by_id(contract_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")
        return self._to_response(obj)

    def create(self, payload: ContractCreate) -> ContractResponse:
        holder = self.right_holder_repo.get_by_id(payload.rights_holder_id)
        if holder is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Правообладатель не найден",
            )

        data = payload.model_dump(exclude={"rights_holder_id"})
        data["right_holder_id"] = holder.id
        try:
            obj = self.repo.create(data)
        except ContractNumberConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Договор с таким номером уже существует",
            ) from e

        response_data = self._to_response(obj)

        # Генерация документа договора
        try:
            generated_path = DocumentService.generate_contract_doc(
                contract=obj,
                holder=holder,
                payload_extra=payload.model_dump(),
            )
            path_obj = Path(generated_path)
            obj = self.repo.update(
                obj.id,
                {"file_path": str(path_obj.parent), "file_name": path_obj.name},
            )
            response_data = self._to_response(obj)
        except Exception as exc:
            error_msg = f"Договор сохранен в БД (ID: {obj.id}), но не удалось сгенерировать файл документа: {exc}"
            print(f"⚠️ {error_msg}", flush=True)
            
            # Передаем предупреждение в ответ фронтенду/клиенту
            if hasattr(response_data, "warning"):
                response_data.warning = error_msg

        return response_data

    def update(self, contract_id: int, payload: ContractUpdate) -> ContractResponse:
        data = payload.model_dump(exclude_unset=True)

        existing = self.repo.get_by_id(contract_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")
        old_file_path, old_file_name = existing.file_path, existing.file_name

        try:
            obj = self.repo.update(contract_id, data)
        except ContractNumberConflictError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Договор с таким номером уже существует",
            ) from e
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")
        self.db.expire_all()
        # Перегенерация файла договора с учетом новых данных
        contract = self.repo.get_by_id(contract_id)
        for key, value in data.items():
            if hasattr(contract, key):
                setattr(contract, key, value)
        

      
        if contract is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")

        contract_dict = {
            "id": getattr(contract, "id", None),
            "contract_number": getattr(contract, "contract_number", None),
            "signed_date": getattr(contract, "signed_date", None),
            "file_path": getattr(contract, "file_path", None),
            "file_name": getattr(contract, "file_name", None),
            "valid_from": getattr(contract, "valid_from", None),
            "valid_to": getattr(contract, "valid_to", None),
        }
        print(f"📄 Перегенерация файла для договора. Данные: {contract_dict}", flush=True)

        holder = contract.right_holder
        if holder is not None:
            try:
                generated_path = DocumentService.generate_contract_doc(
                    contract=contract,
                    holder=holder,
                    payload_extra=data,
                )
                new_path_obj = Path(generated_path)
                contract = self.repo.update(
                    contract_id,
                    {"file_path": str(new_path_obj.parent), "file_name": new_path_obj.name},
                )

                # Если номер договора/правообладатель изменились и файл переехал
                # в другую папку — удаляем старый файл, чтобы не плодить копии.
                if old_file_path and old_file_name:
                    old_full_path = Path(old_file_path) / old_file_name
                    if old_full_path != new_path_obj and old_full_path.exists():
                        old_full_path.unlink(missing_ok=True)
            except Exception as exc:
                print(f"⚠️ Не удалось перегенерировать файл договора: {exc}", flush=True)

        return self._to_response(contract)

    def delete(self, contract_id: int) -> None:
        obj = self.repo.get_by_id(contract_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")

        holder = obj.right_holder

        # Собираем пути к файлам приложений ДО удаления записи из БД
        annex_file_paths = [annex.file_path for annex in obj.annexes if annex.file_path]

        try:
            # БД и SQLAlchemy сами каскадно удалят приложения и их строки
            deleted = self.repo.delete(contract_id)
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Договор используется в других связанных данных и не может быть удалён",
            ) from e

        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")

 
        if holder:
            try:
                contract_dir = DocumentService._get_contract_dir(obj, holder)
                
                # 1. Удаляем файл договора (.docx)
                contract_file = contract_dir / f"Договор_{obj.contract_number}.docx"
                if contract_file.exists():
                    contract_file.unlink(missing_ok=True)
                    print(f"🗑️ Удален файл договора: {contract_file}", flush=True)

                # 2. Удаляем файлы приложений (.xlsx)
                for path_str in annex_file_paths:
                    if path_str:
                        annex_file = Path(path_str)
                        if annex_file.exists():
                            annex_file.unlink(missing_ok=True)
                            print(f"🗑️ Удален файл приложения: {annex_file}", flush=True)

            except Exception as exc:
                print(f"⚠️ Ошибка при удалении файлов с диска: {exc}", flush=True)

    def create_external_contract(self, payload):
        try:
            # 1. Ищем или создаем правообладателя
            holder = None
            if payload.iin_bin:
                holder = self.right_holder_repo.get_by_iin(payload.iin_bin)

            holder_data = {
                "name": payload.name,
                "type": payload.type,
                "alias": payload.alias,
                "email": payload.email,
                "phone": payload.phone,
                "address": payload.address,
                "iin_bin": payload.iin_bin,
                "full_name": payload.full_name,
                "id_document_type": payload.id_document_type,
                "id_document_number": payload.id_document_number,
                "id_document_issued_by": payload.id_document_issued_by,
                "id_document_issue_date": payload.id_document_issue_date,
                "company_name": payload.company_name,
                "director_name": payload.director_name,
                "acting_basis": payload.acting_basis,
                "iban": payload.iban,
                "bank_name": payload.bank_name,
                "bik": payload.bik,
            }

            if holder:
                holder = self.right_holder_repo.update(holder.id, holder_data)
            else:
                holder = self.right_holder_repo.create(holder_data)

            # 2. Создаем договор (direction_type приводим к верхнему регистру для CHECK constraint)
            contract_data = {
                "contract_number": payload.contract_number,
                "right_holder_id": holder.id,
                "direction_type": payload.direction_type.upper() if payload.direction_type else None,
                "signed_date": payload.signed_date,
                "valid_from": payload.valid_from,
                "valid_to": payload.valid_to,
                "status": "DRAFT",
            }

            contract = self.repo.create(contract_data)

            generated_path = DocumentService.generate_contract_doc(
                contract=contract, 
                holder=holder, 
                payload_extra=payload.model_dump()
            )
            path_obj = Path(generated_path)
            contract = self.repo.update(
                contract.id,
                {"file_path": str(path_obj.parent), "file_name": path_obj.name},
            )
            
            # Возвращаем сам объект контракта для валидации по response_model (ContractResponse)
            return contract

        except Exception as e:
            self.db.rollback()
            print(f"🔥 DB SAVE ERROR: {type(e).__name__}: {e}", flush=True)
            raise

    def get_contract_file_path(self, contract_id: int) -> tuple[str, str]:
        obj = self.repo.get_by_id(contract_id)
        if obj is None or not obj.file_path or not obj.file_name:
            raise HTTPException(status_code=404, detail="Договор или файл не найден")

        target_path = os.path.join(obj.file_path, obj.file_name)
        if not os.path.exists(target_path):
            raise HTTPException(status_code=404, detail="Файл физически отсутствует на сервере")

        return target_path, obj.file_name



    _LICENSE_AND_MMP_RE = re.compile(
        r"(?=.*лицензионн\w*\s+договор)(?=.*ммп)",
        re.IGNORECASE | re.DOTALL,
    )
    _PLAIN_NUMBER_RE = re.compile(r"(?<![A-Za-zА-Яа-яЁё0-9-])(\d+)(?![-/0-9])")

    @classmethod
    def extract_license_contract_number(cls, raw_no: Optional[str]) -> Optional[int]:
        """Извлекает числовой номер только если в строке есть и 'Лицензионный договор', и 'ММП'."""
        if not raw_no:
            return None
        text_val = str(raw_no).strip()
        if not cls._LICENSE_AND_MMP_RE.search(text_val):
            return None

        match = cls._PLAIN_NUMBER_RE.search(text_val)
        if not match:
            return None
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return None

    def _exec(self, statement, params: Optional[dict] = None):
        if isinstance(self.db, (Connection, Engine)):
            return self.db.execute(statement, params or {})
        return self.db.execute(statement, params or {})

    def enrich_staging_license_numbers_and_contract_type(
        self,
        upload_id: str,
        staging_table: str = "staging_contract",
    ) -> int:
        """Шаг 1: заполняет contract_number и contract_type = 'DIRECT_ARTIST' только для строк с 'Лицензионный договор', 'ММП' и номером."""
        uid = uuid.UUID(str(upload_id))

        rows = self._exec(
            text(
                f"""
                SELECT id, contract_raw_no
                FROM {staging_table}
                WHERE upload_id = :uid
                """
            ),
            {"uid": uid},
        ).fetchall()

        if not rows:
            return 0

        updates = []
        for row in rows:
            contract_number = self.extract_license_contract_number(row.contract_raw_no)
            if contract_number is not None:
                updates.append(
                    {
                        "id": row.id,
                        "contract_number": contract_number,
                        "contract_type": "DIRECT_ARTIST",
                    }
                )

        if not updates:
            return 0

        self._exec(
            text(
                f"""
                UPDATE {staging_table}
                SET
                    contract_number = :contract_number,
                    contract_type = :contract_type
                WHERE id = :id
                """
            ),
            updates,
        )
        return len(updates)

 

    _HOLDER_PREFIX_RE = re.compile(
            r"^\s*0*(\d+)\s*_?\s*л\s*д(?:[\s._:-]+|(?=[А-ЯЁA-Z]))",
            re.IGNORECASE,
        )

    _PARENS_RE = re.compile(r"\([^)]*\)")
    _NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
    _SPACES_RE = re.compile(r"\s+")

    def _translit(text: str) -> str:
        """Транслитерация кириллицы → латиница, остальные символы без изменений."""
        result = []
        for ch in text:
            low = ch.lower()
            if low in _TRANSLIT_MAP:
                result.append(_TRANSLIT_MAP[low])
            else:
                result.append(low)
        return "".join(result)

    
    @classmethod
    def _extract_tokens(
        cls,
        val: Optional[str],
    ) -> tuple[list[str], list[str]]:
        """
        Возвращает отсортированные списки (anchor_tokens, initials) в латинице.
        Скобки и прочие спецсимволы заменяются на пробел, слова внутри скобок сохраняются.
        """
        if not val:
            return [], []

        transliterated = cls._translit(str(val))
        cleaned = cls._NON_ALNUM_RE.sub(" ", transliterated)
        tokens = [t for t in cls._SPACES_RE.sub(" ", cleaned).strip().split() if t]
        if not tokens:
            return [], []

        anchors = sorted(t for t in tokens if len(t) > 1)
        #initials = sorted(t for t in tokens if len(t) == 1)
        initials = sorted(
            {
                *(t for t in tokens if len(t) == 1),
                *(t[0] for t in anchors if t[0].isalpha()),
            }
        )
        return anchors, initials

    @classmethod   
    def _tokens_similarity(
        cls,
        left: tuple[list[str], list[str]],
        right: tuple[list[str], list[str]],
        fuzzy_threshold: float = 0.68,
    ) -> float:
        anchors_l, initials_l = left
        anchors_r, initials_r = right

        set_l = set(anchors_l) | set(initials_l)
        set_r = set(anchors_r) | set(initials_r)

        denom = max(len(set_l), len(set_r))
        if denom == 0:
            return 0.0

        exact = set_l & set_r
        if len(exact) >= 3:
            return 1.0

        score = float(len(exact))
        rem_l = sorted(set_l - exact)
        rem_r = sorted(set_r - exact)

        used_r: set[str] = set()
        for tok_l in rem_l:
            best_r = None
            best_ratio = 0.0
            for tok_r in rem_r:
                if tok_r in used_r:
                    continue
                ratio = SequenceMatcher(None, tok_l, tok_r).ratio()
                if ratio >= fuzzy_threshold and ratio > best_ratio:
                    best_ratio = ratio
                    best_r = tok_r
            if best_r is not None:
                used_r.add(best_r)
                score += best_ratio

        return score / denom

    @classmethod
    def _name_similarity(cls, left: Optional[str], right: Optional[str]) -> float:
        return cls._tokens_similarity(
            cls._extract_tokens(left),
            cls._extract_tokens(right),
        )

    def link_staging_right_holders(
        self,
        upload_id: str,
        staging_table: str = "staging_contract",
        right_holder_table: str = "right_holder",
        similarity_threshold: float = 0.65,
    ) -> int:
        """Шаг 2: сопоставляет contract_number и токены имени с right_holder и пишет right_holder_id."""
 
        holders = self._exec(
            text(f"SELECT id, name FROM {right_holder_table} WHERE name IS NOT NULL")
        ).fetchall()
        if not holders:
            return 0

        # Предварительно извлекаем токены один раз для каждого правообладателя
        holders_by_number: dict[int, list[tuple[int, tuple[list[str], list[str]]]]] = {}
        for h in holders:
            code_num, cleaned_name = self.parse_right_holder_name(h.name)
            tokens = self._extract_tokens(cleaned_name)
            if code_num is not None and (tokens[0] or tokens[1]):
                holders_by_number.setdefault(code_num, []).append((h.id, tokens))

        if not holders_by_number:
            return 0

        staging_rows = self._exec(
            text(
                f"""
                SELECT id, contract_number, agent_name
                FROM {staging_table}
                WHERE upload_id = :uid
                  AND contract_number IS NOT NULL
                  AND agent_name IS NOT NULL
                """
            ),
            {"uid": upload_id},
        ).fetchall()

        if not staging_rows:
            return 0

        updates = []
        for row in staging_rows:
            candidates = holders_by_number.get(int(row.contract_number))
            if not candidates:
                continue

            agent_tokens = self._extract_tokens(row.agent_name)
            if not agent_tokens[0] and not agent_tokens[1]:
                continue

            scored: list[tuple[float, int]] = []
            for holder_id, holder_tokens in candidates:
                score = self._tokens_similarity(agent_tokens, holder_tokens)
                if score >= similarity_threshold:
                    scored.append((score, holder_id))

            if not scored:
                continue

            scored.sort(key=lambda item: item[0], reverse=True)
            best_score, best_holder_id = scored[0]

            if len(scored) > 1 and abs(best_score - scored[1][0]) < 0.02:
                continue

            updates.append(
                {
                    "id": row.id,
                    "right_holder_id": best_holder_id,
                }
            )

        if not updates:
            return 0

        self._exec(
            text(
                f"""
                UPDATE {staging_table}
                SET right_holder_id = :right_holder_id
                WHERE id = :id
                """
            ),
            updates,
        )
        return len(updates)

    _LEADING_NUM_RE = re.compile(
    r"^\s*0*(\d+)[\s._:\-–—]*(?:л\s*д(?=[\s._:\-–—]+|$))?[\s._:\-–—]*",
    re.IGNORECASE,
)


    @classmethod
    def parse_right_holder_name(cls, raw_name: Optional[str]) -> tuple[Optional[int], str]:
        """Берёт ведущее число в начале строки, при наличии убирает ЛД и возвращает (число, остаток имени)."""
        if not raw_name:
            return None, ""

        text_val = str(raw_name).strip()
        match = cls._LEADING_NUM_RE.match(text_val)
        if not match:
            return None, text_val

        try:
            code_num = int(match.group(1))
        except ValueError:
            code_num = None

        cleaned_name = text_val[match.end():].strip()
        return code_num, cleaned_name

    def sync_from_staging(
            self,
            upload_id: str,
            staging_table: str = "staging_contract",
        ) -> dict[str, int]:
            """Поэтапный разбор данных из staging_contract для указанного upload_id."""
            enriched_count = self.enrich_staging_license_numbers_and_contract_type(
                upload_id=upload_id,
                staging_table=staging_table,
            )
            linked_holders_count = self.link_staging_right_holders(
                upload_id=upload_id,
                staging_table=staging_table,
            )
            return {
                "enriched_count": enriched_count,
                "linked_holders_count": linked_holders_count,
            }

    def export_to_excel(
            self,
            output_dir: str = "/app/storage",
            rights_holder_id: Optional[int] = None,
            status: Optional[str] = None,
            direction_type: Optional[str] = None,
            search: Optional[str] = None,
        ) -> dict:
            os.makedirs(output_dir, exist_ok=True)

            where_clauses = ["1=1"]
            params: dict = {}

            if rights_holder_id is not None:
                where_clauses.append("c.right_holder_id = :rights_holder_id")
                params["rights_holder_id"] = int(rights_holder_id)

            if status:
                status_val = status.value if hasattr(status, "value") else str(status)
                where_clauses.append("c.status = :status")
                params["status"] = status_val

            if direction_type:
                dir_val = direction_type.value if hasattr(direction_type, "value") else str(direction_type)
                where_clauses.append("c.direction_type = :direction_type")
                params["direction_type"] = dir_val

            if search and str(search).strip():
                where_clauses.append(
                    "(CAST(c.contract_number AS TEXT) ILIKE :search OR COALESCE(rh.name, '') ILIKE :search)"
                )
                params["search"] = f"%{str(search).strip()}%"

            where_sql = " AND ".join(where_clauses)

            query = text(
                f"""
                SELECT
                    ROW_NUMBER() OVER (ORDER BY c.contract_number NULLS LAST, c.id) AS "Порядковый номер",
                    COALESCE(CAST(c.contract_number AS TEXT), '-') AS "Номер договора",
                    COALESCE(rh.name, '-') AS "ПО",
                    CONCAT_WS(
                        ' | ',
                        CASE
                            WHEN c.signed_date IS NOT NULL
                            THEN CONCAT('Подписан: ', TO_CHAR(c.signed_date, 'DD.MM.YYYY'))
                            ELSE NULL
                        END,
                        CONCAT(
                            'Действует: ',
                            COALESCE(TO_CHAR(c.valid_from, 'DD.MM.YYYY'), '-'),
                            ' - ',
                            COALESCE(TO_CHAR(c.valid_to, 'DD.MM.YYYY'), 'бессрочно')
                        )
                    ) AS "Даты",
                    COALESCE(CAST(c.status AS TEXT), '-') AS "Статус",
                    COALESCE(
                        STRING_AGG(DISTINCT CAST(ca.annex_number AS TEXT), ', ' ORDER BY CAST(ca.annex_number AS TEXT)),
                        ''
                    ) AS "Приложения"
                FROM contract c
                LEFT JOIN right_holder rh ON rh.id = c.right_holder_id
                LEFT JOIN contract_annex ca ON ca.contract_id = c.id
                WHERE {where_sql}
                GROUP BY
                    c.id,
                    c.contract_number,
                    rh.name,
                    c.signed_date,
                    c.valid_from,
                    c.valid_to,
                    c.status
                ORDER BY c.contract_number NULLS LAST, c.id
                """
            )

            base_filename = f"contracts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            chunk_size = 50000
            total_rows = 0

            result = self._exec(query.execution_options(stream_results=True), params)
            headers = list(result.keys())

            tome_writer = TomeWriterFactory.create(
                "xlsx",
                base_filename,
                output_dir,
                headers,
                max_rows=chunk_size * 5,
            )

            try:
                while True:
                    chunk = result.fetchmany(chunk_size)
                    if not chunk:
                        break
                    tome_writer.write_rows(chunk)
                    total_rows += len(chunk)
            finally:
                tome_writer.close()

            return {
                "status": "success",
                "rows_exported": total_rows,
                "filename": f"{base_filename}_tom_1.xlsx",
                "output_dir": output_dir,
            }
            