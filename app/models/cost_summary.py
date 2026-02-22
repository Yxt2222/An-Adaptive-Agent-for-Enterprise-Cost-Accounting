# app/models/cost_summary.py
from sqlalchemy import (
    Column,
    String,
    Numeric,
    DateTime,
    Integer,
    Enum,
    func,
)
from app.db.base import Base
from app.db.enums import CostSummaryStatus
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from decimal import Decimal

class CostSummary(Base):
    """
    Immutable cost snapshot for a project.
    Represents a single cost calculation result.
    """

    __tablename__ = "cost_summaries"

    # =========
    # 🔒 Identity & ownership
    # =========
    id :Mapped[str] = mapped_column(String(36), primary_key=True, comment="Cost summary UUID")

    project_id :Mapped[str] = mapped_column(String(36), nullable=False, comment="Project ID")

    calculation_version :Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Incremental version of cost calculation for the project",
    )

    # =========
    # 📎 Source file anchors (critical)
    # =========
    material_file_id :Mapped[str] = mapped_column(String(36), nullable=False, comment="Material file ID")
    part_file_id :Mapped[str] = mapped_column(String(36), nullable=False, comment="Part file ID")
    labor_file_id :Mapped[str] = mapped_column(String(36), nullable=False, comment="Labor file ID")
    logistics_file_id :Mapped[str] = mapped_column(String(36), nullable=False, comment="Logistics file ID")

    # =========
    # 💰 Cost snapshot
    # =========
    material_cost :Mapped[Decimal] = mapped_column(Numeric(14, 5), nullable=False, comment="Total material cost")
    part_cost :Mapped[Decimal] = mapped_column(Numeric(14, 5), nullable=False, comment="Total part cost")
    labor_cost :Mapped[Decimal] = mapped_column(Numeric(14, 5), nullable=False, comment="Total labor cost")
    logistics_cost :Mapped[Decimal] = mapped_column(Numeric(14, 5), nullable=False, comment="Total logistics cost")
    total_cost :Mapped[Decimal] = mapped_column(Numeric(16, 5), nullable=False, comment="Total cost")
    # =========
    # 📌 Status & lifecycle
    # =========
    status :Mapped[CostSummaryStatus] = mapped_column(
        Enum(CostSummaryStatus, name="cost_summary_status"),
        nullable=False,
        default=CostSummaryStatus.ACTIVE,
        comment="Status of the cost summary",
    )

    replaces_cost_summary_id :Mapped[str] = mapped_column(
        String(36),
        nullable=True,
        comment="Previous CostSummary ID replaced by this one",
    )

    invalidated_at :Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when this summary was invalidated",
    )

    # =========
    # ⏱ Timestamps
    # =========
    #本次核价完成的时间
    calculated_at :Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Creation timestamp"
    )

    # =========
    # Optional: representation
    # =========
    def __repr__(self) -> str:
        return (
            f"<CostSummary id={self.id} "
            f"project={self.project_id} "
            f"version={self.calculation_version} "
            f"total={self.total_cost}>"
        )
