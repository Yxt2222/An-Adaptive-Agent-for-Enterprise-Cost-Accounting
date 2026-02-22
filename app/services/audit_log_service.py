from typing import Any, Optional, Union
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.db.enums import AuditEntityType, AuditAction

from decimal import Decimal
from datetime import datetime, date

class AuditLogService:
    """
    Centralized service for recording all auditable actions.
    This service is the ONLY place where AuditLog records can be created.
    """

    def __init__(self, db: Session):
        self.db = db
 

    def serialize_audit_value(self, value) -> Any:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)      # 或 str(value)，看你审计偏好
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, (int, float, str, bool)):
            return value
        return str(value)  # 兜底

    def _normalize_entity_type(self, entity_type: Union[str, AuditEntityType]) -> AuditEntityType:
        """
        将字符串或枚举值转换为 AuditEntityType 枚举
        支持多种格式：
        - 枚举值：AuditEntityType.Project
        - 枚举值字符串："project", "name_mapping" 等
        - 枚举名称字符串："Project", "NameMapping" 等
        - 类名："MaterialItem", "PartItem" 等（会转换为 "material_item"）
        """
        if isinstance(entity_type, AuditEntityType):
            return entity_type
        
        # 字符串转枚举：支持大小写不敏感匹配
        entity_type_str = str(entity_type).strip()
        
        # 先尝试直接匹配枚举值（小写）
        for enum_member in AuditEntityType:
            if enum_member.value == entity_type_str.lower():
                return enum_member
        
        # 再尝试匹配枚举名称（大小写不敏感）
        for enum_member in AuditEntityType:
            if enum_member.name.lower() == entity_type_str.lower():
                return enum_member
        
        # 尝试将类名转换为枚举值格式（如 "MaterialItem" -> "material_item"）
        # 使用正则表达式或简单规则：将驼峰命名转换为下划线分隔的小写
        import re
        # 将驼峰命名转换为下划线分隔的小写
        snake_case = re.sub(r'(?<!^)(?=[A-Z])', lambda m: '_', entity_type_str)
        snake_case = snake_case.lower()
        
        for enum_member in AuditEntityType:
            if enum_member.value == snake_case:
                return enum_member
        
        # 如果都不匹配，尝试一些常见的映射
        type_mapping = {
            "project": AuditEntityType.Project,
            "file_record": AuditEntityType.FileRecord,
            "FileRecord": AuditEntityType.FileRecord,
            "name_mapping": AuditEntityType.NameMapping,
            "NameMapping": AuditEntityType.NameMapping,
            "material_item": AuditEntityType.MaterialItem,
            "MaterialItem": AuditEntityType.MaterialItem,
            "part_item": AuditEntityType.PartItem,
            "PartItem": AuditEntityType.PartItem,
            "labor_item": AuditEntityType.LaborItem,
            "LaborItem": AuditEntityType.LaborItem,
            "logistics_item": AuditEntityType.LogisticsItem,
            "LogisticsItem": AuditEntityType.LogisticsItem,
            "cost_summary": AuditEntityType.CostSummary,
            "CostSummary": AuditEntityType.CostSummary,
            "user": AuditEntityType.User,
            "User": AuditEntityType.User,
        }
        
        if entity_type_str in type_mapping:
            return type_mapping[entity_type_str]
        
        if entity_type_str.lower() in type_mapping:
            return type_mapping[entity_type_str.lower()]
        
        # 如果还是找不到，抛出错误
        raise ValueError(f"Unknown entity_type: {entity_type_str}. Valid values: {[e.value for e in AuditEntityType]}")

    def record_create(
        self,
        *,
        project_id: Optional[str],
        entity_type: Union[str, AuditEntityType],
        entity_id: str,
        operator_id: str,
    ) -> None:
        '''
        创建一条创建操作的审计日志
        适用于创建NameMapping, Project, FileRecord, MaterialItem, PartItem, LaborItem, LogisticsItem, CostSummary等实体时调用

        :param project_id: 从属项目ID,可选
        :type project_id: Optional[str]
        :param entity_type: 实体类型：可以是字符串或 AuditEntityType 枚举
        :type entity_type: Union[str, AuditEntityType]
        :param entity_id: 所属实体唯一id
        :type entity_id: str
        :param operator_id: 操作类型："create"，"update"，"confirm"，"invalidate"，"system"
        :type operator_id: str
        '''
        normalized_entity_type = self._normalize_entity_type(entity_type)
        log = AuditLog(
            id=str(uuid4()),
            project_id=project_id,
            entity_type=normalized_entity_type,
            entity_id=entity_id,
            action=AuditAction.create,
            changed_attribute='__all__',
            before_value=None,
            after_value=None,
            operator_id=operator_id,
            timestamp=datetime.now(),
        )
        self.db.add(log)
    def record_update(
        self,
        *,
        project_id: Optional[str],
        entity_type: Union[str, AuditEntityType],
        entity_id: str,
        changed_attribute: str,
        before_value: Any,
        after_value: Any,
        operator_id: str,
    ) -> None:
        '''
        创建一条更新操作的审计日志
        适用于更新NameMapping, Project, FileRecord, MaterialItem, PartItem, LaborItem, LogisticsItem等实体时调用
        :param project_id: 从属项目ID,可选
        :type project_id: Optional[str]
        :param entity_type: 实体类型：可以是字符串或 AuditEntityType 枚举
        :type entity_type: Union[str, AuditEntityType]
        :param entity_id: 所属实体唯一id
        :type entity_id: str
        :param changed_attribute: 变更的属性名称
        :type changed_attribute: str
        :param before_value：修改前的值
        :type before_value: Any
        :param after_value: 修改后的值
        :type after_value: Any
        :param operator_id: 操作用户ID
        :type operator_id: str
        '''
        normalized_entity_type = self._normalize_entity_type(entity_type)
        log = AuditLog(
            id=str(uuid4()),
            project_id=project_id,
            entity_type=normalized_entity_type,
            entity_id=entity_id,
            action=AuditAction.update,
            changed_attribute=changed_attribute,
            before_value=self.serialize_audit_value(before_value),
            after_value=self.serialize_audit_value(after_value),
            operator_id=operator_id,
            timestamp=datetime.now(),
        )
        self.db.add(log)
        
    def record_confirm(
        self,
        *,
        project_id: str,
        entity_type: Union[str, AuditEntityType],
        entity_id: str,
        operator_id: str,
    ) -> None:
        '''
        创建一条确认操作的审计日志
        适用于确认MaterialItem, PartItem, LaborItem, LogisticsItem的status = warning时
        
        :param project_id: 从属项目ID
        :type project_id: str
        :param entity_type: 实体类型：可以是字符串或 AuditEntityType 枚举
        :type entity_type: Union[str, AuditEntityType]
        :param entity_id: 所属实体唯一id
        :type entity_id: str
        :param operator_id: 操作用户ID
        :type operator_id: str
        '''
        normalized_entity_type = self._normalize_entity_type(entity_type)
        log = AuditLog(
            id=str(uuid4()),
            project_id=project_id,
            entity_type=normalized_entity_type,
            entity_id=entity_id,
            action=AuditAction.confirm,
            changed_attribute="__all__",
            before_value=None,
            after_value=None,
            operator_id=operator_id,
            timestamp=datetime.now(),
        )
        self.db.add(log)
    def record_system_update(
        self,
        *,
        project_id: Optional[str],
        entity_type: Union[str, AuditEntityType],
        entity_id: str,
        changed_attribute: str,
        before_value: Any,
        after_value: Any,
    ) -> None:
        '''
        创建一条系统自动更新操作的审计日志:应用场景：
        ValidationService 更新 Item.status
        ValidationService 更新 FileRecord.validation_status
        CostCalculationService：
        冻结 FileRecord
        替代 CostSummary
        
        :param project_id: 从属项目ID,可选
        :type project_id: Optional[str]
        :param entity_type: 实体类型：可以是字符串或 AuditEntityType 枚举
        :type entity_type: Union[str, AuditEntityType]
        :param entity_id: 所属实体唯一id
        :type entity_id: str
        :param changed_attribute: 变更的属性名称
        :type changed_attribute: str
        :param before_value:  修改前的值
        :type before_value: Any
        :param after_value:  修改后的值
        :type after_value: Any
        '''
        normalized_entity_type = self._normalize_entity_type(entity_type)
        log = AuditLog(
            id=str(uuid4()),
            project_id=project_id,
            entity_type=normalized_entity_type,
            entity_id=entity_id,
            action=AuditAction.system,
            changed_attribute=changed_attribute,
            before_value=self.serialize_audit_value(before_value),
            after_value=self.serialize_audit_value(after_value),
            operator_id="SYSTEM",
            timestamp=datetime.now(),
        )
        self.db.add(log)



