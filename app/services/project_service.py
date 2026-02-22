from typing import Optional, List
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.project import Project
from app.services.audit_log_service import AuditLogService
from app.services.name_normalization_service import NameNormalizationService
from app.db.enums import ProjectIdentifierStatus,ProjectNameStatus

class ProjectService:
    """
    Service for managing Project lifecycle and metadata.
    禁止修改 raw_name
    禁止修改 normalized_name
    禁止人工修改 name_status / identifier_status
    禁止 ProjectService 接触 Item / FileRecord / CostSummary

    """

    def __init__(
        self,
        db: Session,
        audit_log_service: AuditLogService,
        name_normalization_service: NameNormalizationService,
    ):
        self.db = db
        self.audit_log_service = audit_log_service
        self.name_normalization_service = name_normalization_service
    def create_project(
        self,
        *,
        raw_name: str,
        business_code: Optional[str],
        contract_code: Optional[str],
        spec_tags: Optional[List[str]],
        operator_id: str,
    ) -> Project:
        '''
        创建新项目
        :param raw_name: 项目原始名字
        :type raw_name: str
        :param business_code: 项目编号
        :type business_code: Optional[str]
        :param contract_code: 合同编号
        :type contract_code: Optional[str]
        :param spec_tags:  项目特殊标签列表
        :type spec_tags: Optional[List[str]]
        :param operator_id: 操作者ID
        :type operator_id: str
        :return: 创建的项目对象
        :rtype: Project
        '''
        project_id = str(uuid4())

        # 1. 名称规范化（只读）
        normalized_name = self.name_normalization_service.normalize_project_name(
            raw_name
        )
        
        # 2. 计算 name_status
        if normalized_name != raw_name:
            name_status = ProjectNameStatus.matched
        else:
            name_status = ProjectNameStatus.unmatched

        # 3. 计算 identifier_status
        identifier_status = self._calculate_identifier_status(
            project_id=project_id,
            business_code=business_code,
            contract_code=contract_code,
        )

        # 4. 初始化 Project（一次性写入最终状态）
        project = Project(
            id=project_id,
            raw_name=raw_name,
            normalized_name=normalized_name,
            business_code=business_code,
            contract_code=contract_code,
            spec_tags=spec_tags,
            name_status=name_status,
            identifier_status=identifier_status,
        )

        self.db.add(project)
        self.db.flush()

        
        # 5. 审计：创建项目
        self.audit_log_service.record_create(
            project_id=project.id,
            entity_type="project",#小写
            entity_id=project.id,
            operator_id=operator_id,
        )

        return project
    def update_project(
        self,
        *,
        project_id: str,
        business_code: Optional[str],
        contract_code: Optional[str],
        spec_tags: Optional[List[str]],
        operator_id: str,
    ) -> Project:
        '''
        更新项目的业务编码、合同编码和特殊标签
        
        :param project_id: 项目ID
        :type project_id: str
        :param business_code: 项目编号
        :type business_code: Optional[str]
        :param contract_code: 合同编号
        :type contract_code: Optional[str]
        :param spec_tags: 项目特殊标签列表
        :type spec_tags: Optional[List[str]]
        :param operator_id: 操作者ID
        :type operator_id: str
        :return: 更新后的项目对象
        :rtype: Project
        '''
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError("Project not found")
        
        if not any([business_code, contract_code, spec_tags]):
            return project  # 无需更新
        
        # 1. business_code
        if  business_code is not None and business_code.strip() != "":
            if business_code != project.business_code:
                self.audit_log_service.record_update(
                    project_id=None,
                    entity_type="project",
                    entity_id=project.id,
                    changed_attribute="business_code",
                    before_value=project.business_code,
                    after_value=business_code,
                    operator_id=operator_id,
                )
                project.business_code = business_code

        # 2. contract_code
        if contract_code is not None and contract_code.strip() != "":
            if contract_code != project.contract_code:
                self.audit_log_service.record_update(
                    project_id=None,
                    entity_type="project",
                    entity_id=project.id,
                    changed_attribute="contract_code",
                    before_value=project.contract_code,
                    after_value=contract_code,
                    operator_id=operator_id,
                )
                project.contract_code = contract_code

        # 3. spec_tags
        if spec_tags is not None:
            if spec_tags != project.spec_tags:
                self.audit_log_service.record_update(
                    project_id=None,
                    entity_type="project",
                    entity_id=project.id,
                    changed_attribute="spec_tags",
                    before_value=project.spec_tags,
                    after_value=spec_tags,
                    operator_id=operator_id,
                )
                project.spec_tags = spec_tags

        # 4. 重新计算 identifier_status（系统行为）
        if any([business_code, contract_code]):
            old_status = project.identifier_status
            new_status = self._calculate_identifier_status(
                project_id=project.id,
                business_code=project.business_code,
                contract_code=project.contract_code,       
            )
            #更新identifier_status字段，并审计
            if new_status != old_status:
                self.audit_log_service.record_system_update(
                    project_id=None,
                    entity_type="project",
                    entity_id=project.id,
                    changed_attribute="identifier_status",
                    before_value=old_status.value if old_status else None,
                    after_value=new_status.value if new_status else None,
                )
                project.identifier_status = new_status

        return project
    def update_business_code(
        self,
        *,
        project_id: str,
        business_code: Optional[str],
        operator_id: str,
    ) -> Project:
        '''
        更新项目的业务编码
        
        :param project_id: 项目ID
        :type project_id: str
        :param business_code: 项目编号
        :type business_code: Optional[str]
        :param operator_id: 操作者ID
        :type operator_id: str
        :return: 更新后的项目对象
        :rtype: Project
        '''
        new_project = self.update_project(
            project_id=project_id,
            business_code=business_code,
            contract_code=None,
            spec_tags=None,
            operator_id=operator_id,
        )
        return new_project
    def update_contract_code(
        self,
        *,
        project_id: str,
        contract_code: Optional[str],
        operator_id: str,
    ) -> Project:
        '''
        更新项目的合同编码
        
        :param project_id: 项目ID
        :type project_id: str
        :param contract_code: 合同编号
        :type contract_code: Optional[str]
        :param operator_id: 操作者ID
        :type operator_id: str
        :return: 更新后的项目对象
        :rtype: Project
        '''
        new_project = self.update_project(
            project_id=project_id,
            business_code=None,
            contract_code=contract_code,
            spec_tags=None,
            operator_id=operator_id,
        )
        return new_project
    def update_spec_tags(
        self,
        *,
        project_id: str,
        spec_tags: Optional[List[str]],
        operator_id: str,
    ) -> Project:
        '''
        更新项目的特殊标签
        
        :param project_id: 项目ID
        :type project_id: str
        :param spec_tags: 项目特殊标签列表
        :type spec_tags: Optional[List[str]]
        :param operator_id: 操作者ID
        :type operator_id: str
        :return: 更新后的项目对象
        :rtype: Project
        '''
        new_project = self.update_project(
            project_id=project_id,
            business_code=None,
            contract_code=None,
            spec_tags=spec_tags,
            operator_id=operator_id,
        )
        return new_project
    
    def _calculate_identifier_status(
        self,
        *,
        project_id: str,
        business_code: Optional[str],
        contract_code: Optional[str],
    ) -> ProjectIdentifierStatus:
        '''
        计算项目的identifier_status: pending/ok/business_code_conflicted/contract_code_conflicted/both_conflicted
        :param project_id: 项目ID
        :type project_id: str
        :param business_code: 业务编码
        :type business_code: Optional[str]
        :param contract_code: 合同编码
        :type contract_code: Optional[str]
        :return:  identifier_status值
        :rtype: str  'pending'/'ok'/'business_code_conflicted'/'contract_code_conflicted'/'both_conflicted'
        '''
        if not business_code and not contract_code:
            return ProjectIdentifierStatus.pending

        business_conflict = False
        contract_conflict = False

        if business_code:
            business_conflict = (
                self.db.query(Project)
                .filter(
                    Project.business_code == business_code,
                    Project.id != project_id,
                )
                .count()
                > 0
            )

        if contract_code:
            contract_conflict = (
                self.db.query(Project)
                .filter(
                    Project.contract_code == contract_code,
                    Project.id != project_id,
                )
                .count()
                > 0
            )

        if business_conflict and contract_conflict:
            return ProjectIdentifierStatus.both_conflicted
        if business_conflict:
            return ProjectIdentifierStatus.business_code_conflicted
        if contract_conflict:
            return ProjectIdentifierStatus.contract_code_conflicted
        return ProjectIdentifierStatus.ok

      


