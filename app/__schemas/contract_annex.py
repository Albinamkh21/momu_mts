from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class AnnexItemPayload(BaseModel):
    """Схема для одной строки таблицы приложения (произведение и авторы)."""
    line_number: int = Field(..., description="№ п/п")
    code: Optional[str] = Field(None, description="ISRC или внутренний код трека")
    track_title: str = Field(..., description="Название песни")
    artist_name: str = Field(..., description="Исполнитель")
    
    related_rights_percent: Decimal = Field(..., ge=0, le=100, description="% смежных прав")
    
    composer_name: str = Field(..., description="Автор музыки (композитор)")
    composer_percent: Decimal = Field(..., ge=0, le=100, description="% прав на музыку")
    
    lyricist_name: str = Field(..., description="Автор текста")
    lyricist_percent: Decimal = Field(..., ge=0, le=100, description="% прав на текст")


class IncomingAnnexPayload(BaseModel):
    """Корневая схема входящего приложения от сайта/Telegram/API."""
    contract_number: str = Field(..., description="Номер договора, к которому привязывается приложение")
    annex_number: str = Field(..., description="Номер приложения (например, '1' или '2-1')")
    doc_date: date = Field(..., description="Дата документа")
    
    items: List[AnnexItemPayload] = Field(..., min_length=1, description="Список треков и авторов")


class AnnexItemCreate(BaseModel):
    """Схема для добавления одной строки в существующее приложение.

    `line_number` не передаётся — назначается репозиторием автоматически
    (максимальный существующий номер + 1).
    """
    code: Optional[str] = Field(None, description="ISRC или внутренний код трека")
    track_title: str = Field(..., description="Название песни")
    artist_name: str = Field(..., description="Исполнитель")

    related_rights_percent: Decimal = Field(..., ge=0, le=100, description="% смежных прав")

    composer_name: str = Field(..., description="Автор музыки (композитор)")
    composer_percent: Decimal = Field(..., ge=0, le=100, description="% прав на музыку")

    lyricist_name: str = Field(..., description="Автор текста")
    lyricist_percent: Decimal = Field(..., ge=0, le=100, description="% прав на текст")


class AnnexItemUpdate(BaseModel):
    """Схема для редактирования строки приложения — все поля опциональны."""
    line_number: Optional[int] = Field(None, description="№ п/п")
    code: Optional[str] = None
    track_title: Optional[str] = None
    artist_name: Optional[str] = None
    related_rights_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    composer_name: Optional[str] = None
    composer_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    lyricist_name: Optional[str] = None
    lyricist_percent: Optional[Decimal] = Field(None, ge=0, le=100)


class AnnexStatus(str, Enum):
    DRAFT = "DRAFT"
    PROCESSING = "PROCESSING"
    PARSED = "PARSED"
    FAILED = "FAILED"


class ContractAnnexCreate(BaseModel):
    """Схема для ручного создания приложения через UI (вместе с начальными строками)."""
    annex_number: str = Field(..., description="Номер приложения (например, '1' или '2-1')")
    doc_date: date = Field(..., description="Дата документа")
    status: AnnexStatus = Field(AnnexStatus.DRAFT, description="Статус приложения")
    items: List[AnnexItemPayload] = Field(..., min_length=1, description="Список треков и авторов")


class ContractAnnexUpdate(BaseModel):
    """Схема для редактирования шапки приложения. Строки (items) редактируются отдельными эндпоинтами."""
    annex_number: Optional[str] = None
    doc_date: Optional[date] = None
    status: Optional[AnnexStatus] = None


class AnnexItemResponse(BaseModel):
    """Строка таблицы приложения, как она сохранена в БД."""
    id: int
    line_number: int
    code: Optional[str] = None
    track_title: str
    artist_name: str
    related_rights_percent: Decimal
    composer_name: str
    composer_percent: Decimal
    lyricist_name: str
    lyricist_percent: Decimal
    track_id: Optional[int] = None

    model_config = {"from_attributes": True}


class ContractAnnexResponse(BaseModel):
    """Ответ API после создания приложения к договору."""
    id: int
    contract_id: int
    annex_number: str
    doc_date: date
    status: AnnexStatus
    file_path: Optional[str] = Field(None, description="Путь к сгенерированному .xlsx файлу приложения")
    items: List[AnnexItemResponse] = []

    model_config = {"from_attributes": True}


class ContractAnnexListItem(BaseModel):
    """Строка списка приложений договора (без полной табличной части)."""
    id: int
    contract_id: int
    annex_number: str
    doc_date: date
    status: AnnexStatus
    file_path: Optional[str] = None
    items_count: int = 0

    model_config = {"from_attributes": True}


class ContractAnnexListResponse(BaseModel):
    items: List[ContractAnnexListItem]
    total: int