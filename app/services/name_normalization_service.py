from typing import Optional
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.name_mapping import NameMapping, NameDomain
from app.services.audit_log_service import AuditLogService

class NameNormalizationService:
    '''
    Service for normalizing raw names into canonical normalized names.
    This service manages NameMapping as a knowledge asset.
    绝对禁止的事项：
    不允许 NameNormalizationService 修改 Project / Item
    不允许在 normalize 中写日志
    不允许自动生成映射
    不允许绕过 Service 直接操作 NameMapping ORM
    '''

    def __init__(self, db: Session, audit_log_service: AuditLogService):
        self.db = db
        self.audit_log_service = audit_log_service
    def normalize(
        self,
        *,
        domain: NameDomain,
        raw_name: str,
    ) -> str:
        '''
        Normalize a raw name into its canonical normalized form based on the specified domain.
        :param domain: 名字映射领域："project","material","part","labor_group"
        :type domain: NameDomain
        :param raw_name: 原始名字
        :type raw_name: str
        :return: 返回规范化后的名字；如果没有找到对应的规范化名字，则返回原始名字
        :rtype: str
        '''
        mapping = (
            self.db.query(NameMapping)
            .filter(
                NameMapping.domain == domain,
                NameMapping.raw_name == raw_name,
                NameMapping.is_active.is_(True),
            )
            .one_or_none()
        )

        if mapping:
            return mapping.normalized_name

        return raw_name
    
    def normalize_project_name(self, raw_name: str) -> str:
        #对project的名称进行规范化
        
        return self.normalize(domain=NameDomain.PROJECT, raw_name=raw_name)

    def normalize_material_name(self, raw_name: str) -> str:
        #对materialitem的名称进行规范化

        return self.normalize(domain=NameDomain.MATERIAL, raw_name=raw_name)

    def normalize_part_name(self, raw_name: str) -> str:
       #对partitem的名称进行规范化
        return self.normalize(domain=NameDomain.PART, raw_name=raw_name)

    def normalize_labor_group_name(self, raw_name: str) -> str:  
        #对laboritem的名称进行规范化   
        return self.normalize(domain=NameDomain.LABOR_GROUP, raw_name=raw_name)
    
    def create_mapping(
        self,
        *,
        domain: NameDomain,
        raw_name: str,
        normalized_name: str,
        operator_id: str,
    ) -> NameMapping:
        '''
        创建一条新的名字映射记录
        该操作会创建一条NameMapping记录，并确保在同一domain下，raw_name的唯一性
        :param domain: 名字映射领域："project","material","part","labor_group"
        :type domain: NameDomain
        :param raw_name: 原始名字
        :type raw_name: str
        :param normalized_name: 规范化后的名字
        :type normalized_name: str
        :param operator_id: 操作者ID
        :type operator_id: str
        :return: 创建的NameMapping对象
        :rtype: NameMapping
        '''
        mapping = NameMapping(
            id=str(uuid4()),
            domain=domain,
            raw_name=raw_name,
            normalized_name=normalized_name,
            is_active=True,
            created_by=operator_id,
        )

        self.db.add(mapping)

        try:
            self.db.flush()  # 触发唯一约束
        except IntegrityError:
            raise ValueError(
                f"Active mapping already exists for domain={domain.value}, raw_name='{raw_name}'"
            )

        # 审计：创建语义资产
        self.audit_log_service.record_create(
            project_id=None,
            entity_type="NameMapping",
            entity_id=mapping.id,
            operator_id=operator_id,
        )

        return mapping
    
    def replace_mapping(
        self,
        *,
        mapping_id: str,
        new_normalized_name: str,
        operator_id: str,
    ) -> NameMapping:
        '''
        替换一条已有的名字映射记录
        :param mapping_id: 需要替换的NameMapping记录ID
        :type mapping_id: str
        :param new_normalized_name: 新的规范化名字
        :type new_normalized_name: str
        :param operator_id: 操作者ID
        :type operator_id: str
        :return: 新创建的NameMapping对象
        '''
        #根据主键ID，搜索旧的映射记录
        old_mapping = self.db.get(NameMapping, mapping_id)
        if not old_mapping or not old_mapping.is_active:
            raise ValueError("Mapping not found or already inactive")

        # 1. 失效旧映射
        old_mapping.is_active = False

        # 2. 创建新映射
        new_mapping = NameMapping(
            id=str(uuid4()),
            domain=old_mapping.domain,
            raw_name=old_mapping.raw_name,
            normalized_name=new_normalized_name,
            is_active=True,
            created_by=operator_id,
        )
        self.db.add(new_mapping)

        # 3. 审计（语义替代）
        self.audit_log_service.record_system_update(
            project_id=None,
            entity_type="NameMapping",
            entity_id=old_mapping.id,
            changed_attribute="is_active",
            before_value=True,
            after_value=False,
        )

        self.audit_log_service.record_create(
            project_id=None,
            entity_type="NameMapping",
            entity_id=new_mapping.id,
            operator_id=operator_id,
        )

        return new_mapping

    def deactivate_mapping(
        self,
        *,
        mapping_id: str,
        operator_id: str,
    ) -> None:
        '''
        失效一条名字映射记录
        
        :param mapping_id:  需要失效的NameMapping记录ID
        :type mapping_id: str
        :param operator_id:  操作者ID
        :type operator_id: str
        '''
        mapping = self.db.get(NameMapping, mapping_id)
        if not mapping or not mapping.is_active:
            raise ValueError("Mapping not found or already inactive")
        old_status = mapping.is_active
        if old_status:
            return  # 已经是失效状态，无需重复操作
        else:
            mapping.is_active = False
            self.audit_log_service.record_update(
                project_id=None,
                entity_type="NameMapping",
                entity_id=mapping.id,
                changed_attribute="is_active",
                before_value=True,
                after_value=False,
                operator_id=operator_id,
            )


