"""ReportRepository — read/delete access to the `report` table for the report history tab."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from models import Partners, Report, RightCategory, RightUsageType

# Whitelist of columns that can be sorted on (protects against SQL injection via sort_by).
SORTABLE_FIELDS: dict[str, Any] = {
    "id": Report.id,
    "partner_name": Partners.service_name,
    "right_category_name": RightCategory.name,
    "right_usage_type_name": RightUsageType.code,
    "report_month": Report.report_month,
    "report_year": Report.report_year,
    "play_count": Report.play_count,
    "payout_amount": Report.payout_amount,
    "price_per_play": Report.price_per_play,
    "created_at": Report.created_at,
}


class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        *,
        partner_id: Optional[int] = None,
        right_category_id: Optional[int] = None,
        right_usage_type_id: Optional[int] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        month_from: Optional[int] = None,
        month_to: Optional[int] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[Report, Partners, RightCategory, RightUsageType]], int]:
        query = (
            self.db.query(Report, Partners, RightCategory, RightUsageType)
            .join(Partners, Report.partner_id == Partners.id)
            .join(RightCategory, Report.right_category_id == RightCategory.id)
            .join(RightUsageType, Report.right_usage_type_id == RightUsageType.id)
        )

        if partner_id is not None:
            query = query.filter(Report.partner_id == partner_id)
        if right_category_id is not None:
            query = query.filter(Report.right_category_id == right_category_id)
        if right_usage_type_id is not None:
            query = query.filter(Report.right_usage_type_id == right_usage_type_id)
        if year_from is not None:
            query = query.filter(Report.report_year >= year_from)
        if year_to is not None:
            query = query.filter(Report.report_year <= year_to)
        if month_from is not None:
            query = query.filter(Report.report_month >= month_from)
        if month_to is not None:
            query = query.filter(Report.report_month <= month_to)

        total = query.count()

        sort_col = SORTABLE_FIELDS.get(sort_by, Report.created_at)
        order_fn = asc if sort_dir == "asc" else desc
        query = query.order_by(order_fn(sort_col))

        rows = query.offset(offset).limit(limit).all()
        return rows, total

    def delete_many(self, ids: list[int]) -> int:
        if not ids:
            return 0
        deleted = (
            self.db.query(Report)
            .filter(Report.id.in_(ids))
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted
