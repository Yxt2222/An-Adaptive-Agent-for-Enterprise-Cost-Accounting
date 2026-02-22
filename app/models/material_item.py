# app/models/material_item.py
from sqlalchemy import (
    Column,
    String,
    Numeric,
)
from decimal import Decimal
from app.db.base import Base
from app.models.mixins.base_cost_item import BaseCostItemMixin
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class MaterialItem(Base, BaseCostItemMixin):
    """
    Standardized material cost item.
    Derived from material-related FileRecord.
    """

    __tablename__ = "material_items"

    # =========
    # 🔤 Naming (material-specific)
    # =========
    raw_name :Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Raw material name from Excel, immutable",
    )

    normalized_name :Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Standardized material name, editable with AuditLog",
    )

    # =========
    # 📐 Specification
    # =========
    spec :Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Specification / model",
    )

    material_grade :Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="Material grade / type",
    )

    supplier :Mapped[str] = mapped_column(
        String(255),#最多 255 个字符长度的字符串
        nullable=True,
        comment="Supplier name",
    )

    # =========
    # 🔢 Quantity & pricing
    # =========
    quantity :Mapped[Decimal] = mapped_column(
        Numeric(12, 5),#保留三位小数以支持重量类材料，总位数12位
        nullable=True,
        comment="Quantity(optional)",
    )

    unit :Mapped[str] = mapped_column(
        String(50),#最多 50 个字符长度的字符串
        nullable=True,
        comment="Unit of quantity",
    )

    weight_kg :Mapped[Decimal] = mapped_column(
        Numeric(12, 5),
        nullable=True,
        comment="Reference weight in kg (required)",
    )

    unit_price :Mapped[Decimal] = mapped_column(
        Numeric(12, 5),
        nullable=True,
        comment="Unit price (per ton or per unit depending on material)",
    )

    subtotal :Mapped[Decimal] = mapped_column(
        Numeric(14, 5),
        nullable=True,
        comment="Subtotal from Excel or system-calculated",
    )

    # =========
    # Optional: representation
    # =========
    def __repr__(self) -> str:
        return (
            f"<MaterialItem id={self.id} "
            f"name={self.normalized_name or self.raw_name} "
            f"subtotal={self.subtotal}>"
        )
