from app.services.validation_service import ValidationReport, ItemValidationResult
from pydantic import BaseModel
from typing import List


class ValidationIssueDTO(BaseModel):
    item_id: str
    status: str  # "ok" | "warning" | "blocked" | "confirmed"

    error_codes: List[str]
    messages: List[str]

    explanation: str

class ValidationSummaryDTO(BaseModel):
    total_items: int
    ok_count: int
    warning_count: int
    confirmed_count: int
    blocked_count: int

    is_ready_for_summary: bool

class ValidationReportDTO(BaseModel):
    summary: ValidationSummaryDTO

    blocked_items: List[ValidationIssueDTO]
    warning_items: List[ValidationIssueDTO]

    @classmethod
    def from_domain_model(cls, report: ValidationReport) -> "ValidationReportDTO":

        summary = ValidationSummaryDTO(
            total_items=report.total_items,
            ok_count=report.ok_count,
            warning_count=report.warning_count,
            confirmed_count=report.confirmed_count,
            blocked_count=report.blocked_count,
            is_ready_for_summary=(report.blocked_count == 0 and report.warning_count == 0)
        )

        def convert_item(item: ItemValidationResult):
            return ValidationIssueDTO(
                item_id=item.item_id,
                status=item.status,
                error_codes=item.error_codes,
                messages=item.messages,
                explanation="; ".join(item.messages)
            )

        return cls(
            summary=summary,
            blocked_items=[convert_item(i) for i in report.blocked_items],
            warning_items=[convert_item(i) for i in report.warning_items]
        )
