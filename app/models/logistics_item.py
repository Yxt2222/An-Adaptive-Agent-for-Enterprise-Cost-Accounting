# app/models/logistics_item.py
from sqlalchemy import (
    Column,
    String,
    Numeric,
    Enum,
)
from app.db.base import Base
from app.db.enums import LogisticsType
from app.models.mixins.base_cost_item import BaseCostItemMixin
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class LogisticsItem(Base, BaseCostItemMixin):
    """
    Logistics / installation cost item.
    Represents a single logistics-related cost entry.
    """

    __tablename__ = "logistics_items"

    # =========
    # 🚚 Cost type
    # =========
    type :Mapped[LogisticsType] = mapped_column(
        Enum(LogisticsType, name="logistics_type"),
        nullable=False,
        comment="Logistics cost category",
    )

    # =========
    # 📝 Description
    # =========
    description :Mapped[str] = mapped_column(
        String(500),
        nullable=True,
        comment="Cost description, editable with AuditLog",
    )

    # =========
    # 💰 Cost amount
    # =========
    subtotal :Mapped[float] = mapped_column(
        Numeric(14, 2),
        nullable=True,
        comment="Logistics cost subtotal",
    )

    # =========
    # Optional: representation
    # =========
    def __repr__(self) -> str:
        return (
            f"<LogisticsItem id={self.id} "
            f"type={self.type.value} "
            f"subtotal={self.subtotal}>"
        )
