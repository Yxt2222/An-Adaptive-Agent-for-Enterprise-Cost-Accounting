# app/models/schema_instance.py
"""
SchemaInstance 数据库模型
用于持久化 SchemaObject 的具体实例
"""
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    JSON,
    DateTime,
    func,
)
from app.db.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime


class SchemaInstanceModel(Base):
    """
    SchemaObject 的数据库持久化实例
    """
    __tablename__ = "schema_instances"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Instance UUID")

    # 实例信息
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Instance name, e.g., 'BatchEditItemsInput_Instance1'"
    )

    # 所属 Schema 信息
    schema_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Name of the Schema this instance belongs to"
    )

    schema_version: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="Version of the Schema"
    )

    # 字段值（JSON 存储）
    field_values: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Field values as JSON, key is field name"
    )

    # 元数据
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Optional description of this instance"
    )

    created_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Creator of this instance"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Creation timestamp"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last update timestamp"
    )

class ChangeRecordModel(Base):
    __tablename__ = "change_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        comment="Change record UUID"
    )
    object_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Object name"
    )
    version_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Version ID"
    )
    operator: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Operator"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timestamp"
    )
    change_description: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Change description"
    )

class SemanticObjectModel(Base):
    __tablename__ = "semantic_objects"
    
    """经过 Transformer 转换的 Agent-ready 输入对象"""
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        comment="Instance UUID"
        )
    
    agent_run_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="Agent run ID"
        )
    
    object_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Object name"
        )
    standardized_fields: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Standardized fields"
        )
    schema_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Schema name"
        )
    schema_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Schema version"
        )
    template_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Template name"
        )
    template_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Template version"
        )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timestamp"
        )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Creation timestamp"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last update timestamp"
    )