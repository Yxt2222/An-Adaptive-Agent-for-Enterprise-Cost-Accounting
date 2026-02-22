# app/models/part_item.py
from sqlalchemy import (
    Column,
    String,
    Numeric,
    Integer
)
from app.db.base import Base
from app.models.mixins.base_cost_item import BaseCostItemMixin
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from decimal import Decimal
class PartItem(Base, BaseCostItemMixin):
    """
    Standardized part (component) cost item.
    Derived from part-related FileRecord.
    """

    __tablename__ = "part_items"

    # =========
    # 🔤 Naming (part-specific)
    # =========
    raw_name :Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Raw part name from Excel, immutable",
    )

    normalized_name :Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Standardized part name, editable with AuditLog",
    )

    # =========
    # 📐 Specification
    # =========
    spec :Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Specification / model of part",
    )

    supplier :Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Supplier or manufacturer",
    )

    # =========
    # 🔢 Quantity & pricing
    # =========
    quantity :Mapped[Decimal] = mapped_column(
        Numeric(12, 5),
        nullable=True,
        comment="Quantity of parts",
    )

    unit :Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        comment="Unit of quantity",
    )

    unit_price :Mapped[Decimal] = mapped_column(
        Numeric(12, 5),
        nullable=True,
        comment="Unit price of part",
    )

    subtotal :Mapped[Decimal] = mapped_column(
        Numeric(14, 5),
        nullable=True,
        comment="Subtotal from Excel or system-calculated",
    )

    bundle_key :Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment="bundle_key to link parts in a bundle",
    )

    # =========
    # Optional: representation
    # =========
    def __repr__(self) -> str:
        return (
            f"<PartItem id={self.id} "
            f"name={self.normalized_name or self.raw_name} "
            f"subtotal={self.subtotal}>"
        )
