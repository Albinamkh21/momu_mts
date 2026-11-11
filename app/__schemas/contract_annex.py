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


class AnnexStatus(str, Enum):
    DRAFT = "DRAFT"
    PROCESSING = "PROCESSING"
    PARSED = "PARSED"
    FAILED = "FAILED"


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