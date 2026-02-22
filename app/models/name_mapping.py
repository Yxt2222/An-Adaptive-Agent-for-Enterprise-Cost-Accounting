#NameMapping ORM model
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.user import User
from app.db.base import Base
from app.db.enums import NameDomain
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, Enum, ForeignKey, Index, UniqueConstraint, Column
from sqlalchemy.sql import func, text

 
class NameMapping(Base):
    __tablename__ = "name_mappings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        comment="Primary key of name mapping"
    )

    domain: Mapped[NameDomain] = mapped_column(
        Enum(NameDomain, name="name_domain_enum"),
        nullable=False,
        comment="Domain of the name mapping"
    )

    raw_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original raw name entered by user"
    )

    normalized_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Normalized canonical name used by system"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        comment="Whether this mapping is currently active"
    )

    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        comment="User who created this mapping"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Creation timestamp"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp"
    )

    creator: Mapped["User"] = relationship("User", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "domain",
            "raw_name",
            "is_active",
            name="uq_domain_raw_active"
        ),
        Index(
            "idx_name_mapping_lookup",
            "domain",
            "raw_name",
            "is_active"
        ),
    )
'''
class NameMapping(Base):
    __tablename__ = "name_mappings"

    id = Column(
        String(36),
        primary_key=True,
        comment="Primary key of name mapping"
    )

    domain = Column(
        Enum(NameDomain, name="name_domain_enum"),
        nullable=False,
        comment="Domain of the name mapping (project/material/part/labor_group)"
    )

    raw_name = Column(
        String(255),
        nullable=False,
        comment="Original raw name entered by user"
    )

    normalized_name = Column(
        String(255),
        nullable=False,
        comment="Normalized canonical name used by system"
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        comment="Whether this mapping is currently active"
    )

    created_by = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        comment="User who created this mapping"
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Creation timestamp"
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp"
    )

    # Optional relationship (if User ORM exists)
    creator = relationship("User", lazy="joined")
    __table_args__ = (
        # 同一 domain + raw_name 只能有一个 active 映射
        UniqueConstraint(
            "domain",
            "raw_name",
            "is_active",
            name="uq_domain_raw_active"
        ),

        # 查询性能优化（normalize 高频路径）
        Index(
            "idx_name_mapping_lookup",
            "domain",
            "raw_name",
            "is_active"
        ),
    )
'''
 