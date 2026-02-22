from app.models.cost_summary import CostSummary
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime


class CostBreakdownDTO(BaseModel):
    material: float
    part: float
    labor: float
    logistics: float
    total: float


class CostSummaryDTO(BaseModel):
    id: str
    project_id: str
    version: int

    status: str

    cost: CostBreakdownDTO

    source_files: Dict[str, str]

    calculated_at: datetime

    replaces_cost_summary_id: Optional[str] = None

    @classmethod
    def from_domain_model(cls, cost_summary: CostSummary) -> "CostSummaryDTO":
        return cls(
            id=cost_summary.id,
            project_id=cost_summary.project_id,
            version=cost_summary.calculation_version,
            status=cost_summary.status.value,
            cost=CostBreakdownDTO(
                material=float(cost_summary.material_cost or 0),
                part=float(cost_summary.part_cost or 0),
                labor=float(cost_summary.labor_cost or 0),
                logistics=float(cost_summary.logistics_cost or 0),
                total=float(cost_summary.total_cost or 0)
            ),
            source_files={'material': cost_summary.material_file_id,
                        'part': cost_summary.part_file_id,
                        'labor': cost_summary.labor_file_id,
                        'logistics': cost_summary.logistics_file_id},
            calculated_at=cost_summary.calculated_at,
            replaces_cost_summary_id=cost_summary.replaces_cost_summary_id
        )