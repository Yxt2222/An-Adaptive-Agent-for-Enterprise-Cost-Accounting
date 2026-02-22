# app/models/audit_log.py
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Enum,
    JSON,
    func,
    TypeDecorator,
)
from app.db.base import Base
from app.db.enums import AuditEntityType, AuditAction
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Any


class AuditEntityTypeEnum(TypeDecorator):
    """
    自定义类型装饰器，用于处理字符串到枚举的转换
    兼容数据库中可能存在的旧数据（字符串格式）
    """
    impl = String
    cache_ok = True
    
    def __init__(self):
        super().__init__(length=50)
    
    def process_bind_param(self, value: Any, dialect) -> str:
        """写入数据库时的处理"""
        if isinstance(value, AuditEntityType):
            return value.value
        if isinstance(value, str):
            # 尝试将字符串转换为枚举值
            for enum_member in AuditEntityType:
                if enum_member.value == value.lower() or enum_member.name.lower() == value.lower():
                    return enum_member.value
            return value.lower()
        return str(value).lower() if value else None
    
    def process_result_value(self, value: Any, dialect) -> AuditEntityType:
        """从数据库读取时的处理"""
        if value is None:
            return None
        if isinstance(value, AuditEntityType):
            return value
        # 将字符串值转换为枚举
        if isinstance(value, str):
            value_lower = value.lower().strip()
            # 先尝试匹配枚举值
            for enum_member in AuditEntityType:
                if enum_member.value == value_lower:
                    return enum_member
                if enum_member.name.lower() == value_lower:
                    return enum_member
            # 如果找不到匹配的枚举，尝试一些常见映射
            mapping = {
                "project": AuditEntityType.Project,
                "file_record": AuditEntityType.FileRecord,
                "name_mapping": AuditEntityType.NameMapping,
                "material_item": AuditEntityType.MaterialItem,
                "part_item": AuditEntityType.PartItem,
                "labor_item": AuditEntityType.LaborItem,
                "logistics_item": AuditEntityType.LogisticsItem,
                "cost_summary": AuditEntityType.CostSummary,
                "costsummary": AuditEntityType.CostSummary,  # 兼容可能的拼写错误
                "user": AuditEntityType.User,
            }
            if value_lower in mapping:
                return mapping[value_lower]
            # 如果还是找不到，抛出错误以便调试
            raise ValueError(f"Cannot convert '{value}' to AuditEntityType. Valid values: {[e.value for e in AuditEntityType]}")
        return value


class AuditLog(Base):
    __tablename__ = "audit_logs"

    # =========
    # 🔒 Immutable fields (no update, no delete)
    # =========
    id :Mapped[str] = mapped_column(String(36), primary_key=True,comment="Audit log UUID")

    project_id :Mapped[str] = mapped_column(String(36), nullable=True,comment="Associated project ID, if applicable")

    entity_type :Mapped[AuditEntityType] = mapped_column(
        AuditEntityTypeEnum(),
        nullable=False,
        comment="Type of the audited entity"
    )

    entity_id :Mapped[str] = mapped_column(String(36), nullable=False, comment="UUID of the audited entity")

    action :Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"),
        nullable=False,
        comment="Type of action performed on the entity"
    )

    changed_attribute :Mapped[str] = mapped_column(String(100), nullable=False,comment="Attribute that was changed")

    before_value :Mapped[dict] = mapped_column(JSON, nullable=True,comment="Value before the change")  # 非每一个变更都有前值，后值，如create
    after_value :Mapped[dict] = mapped_column(JSON, nullable=True,comment="Value after the change")    # 非每一个变更都有前值，后值，如delete

    operator_id :Mapped[str] = mapped_column(String(36), nullable=False,comment="User ID of the operator who performed the action")

    timestamp :Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the action was performed"
    )

    # =========
    # Optional: representation
    # =========
    def __repr__(self) -> str:
        return (
            f"<AuditLog entity={self.entity_type.value} "
            f"entity_id={self.entity_id} "
            f"action={self.action.value}>"
        )
