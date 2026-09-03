"""ReportHistoryService — business logic for the report history tab (list/delete `report` rows)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from __crud.report_repository import ReportRepository
from __schemas.reports import ReportHistoryItem


class ReportHistoryService:
    def __init__(self, db: Session):
        self.repo = ReportRepository(db)

    def list_reports(
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
    ) -> tuple[list[ReportHistoryItem], int]:
        rows, total = self.repo.get_all(
            partner_id=partner_id,
            right_category_id=right_category_id,
            right_usage_type_id=right_usage_type_id,
            year_from=year_from,
            year_to=year_to,
            month_from=month_from,
            month_to=month_to,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

        items = [
            ReportHistoryItem(
                id=report.id,
                partner_id=report.partner_id,
                partner_name=f"{partner.code or partner.id} - {partner.service_name}",
                right_category_id=report.right_category_id,
                right_category_name=right_category.name,
                right_usage_type_id=report.right_usage_type_id,
                right_usage_type_name=(
                    f"{right_usage_type.code} - {right_usage_type.name}"
                    if right_usage_type.name
                    else right_usage_type.code
                ),
                report_month=report.report_month,
                report_year=report.report_year,
                play_count=report.play_count,
                payout_amount=float(report.payout_amount) if report.payout_amount is not None else None,
                price_per_play=float(report.price_per_play) if report.price_per_play is not None else None,
                upload_id=report.upload_id,
                created_at=report.created_at,
            )
            for report, partner, right_category, right_usage_type in rows
        ]
        return items, total

    def delete_reports(self, ids: list[int]) -> int:
        return self.repo.delete_many(ids)
