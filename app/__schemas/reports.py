"""Pydantic schemas for the report history endpoints (GET/DELETE /report)."""
from __future__ import annotations

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ReportHistoryItem(BaseModel):
    id: int
    partner_id: int
    partner_name: str
    right_category_id: int
    right_category_name: str
    right_usage_type_id: int
    right_usage_type_name: str
    report_month: int
    report_year: int
    play_count: Optional[int] = None
    payout_amount: Optional[float] = None
    price_per_play: Optional[float] = None
    upload_id: Optional[str] = None
    created_at: Optional[datetime.datetime] = None

    model_config = {"from_attributes": True}


class ReportDeleteRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1)
