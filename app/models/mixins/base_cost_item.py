# app/models/mixins/base_cost_item.py
from typing import Optional
from sqlalchemy import String, DateTime, Enum, Boolean, func, text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.db.enums import CostItemStatus

class BaseCostItemMixin:
    """
    Base mixin for all cost items (material / part / labor / logistics).

    Invariants:
    - Immutable identity
    - Belongs to one project
    - Derived from exactly one FileRecord
    - Status maintained by system
    """
    # =========
    # Identity & source
    # =========
    id :Mapped[str] = mapped_column(String(36), primary_key=True,comment="Cost item UUID")

    project_id :Mapped[str] = mapped_column(String(36), nullable=False,comment="Associated project ID")
    source_file_id :Mapped[str] = mapped_column(String(36), nullable=False,comment="Source FileRecord ID")
    # =========
    # 🔁 System maintained status
    # =========
    status :Mapped[CostItemStatus] = mapped_column(
        Enum(CostItemStatus),
        nullable=False,
        default=CostItemStatus.warning,
        comment="Status of the cost item maintained by system"
    )
    is_calculable :Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,                 # ORM 层默认
        server_default=text("true"),  # DB 层默认（PostgreSQL）
        comment="Whether this item participates in cost calculation (bundle anchor only)"
    )
    # =========
    # ⏱ Timestamps
    # =========
    created_at :Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Creation timestamp"
    )

    updated_at :Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last update timestamp"
    )
 