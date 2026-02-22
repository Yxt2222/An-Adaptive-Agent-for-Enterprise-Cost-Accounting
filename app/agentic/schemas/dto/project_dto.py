from app.models.project import Project
from pydantic import BaseModel
from typing import List,Optional
from datetime import datetime

class ProjectBusinessEditableInfo(BaseModel):
    business_code:Optional[str]
    contract_code:Optional[str]
    normalized_name:Optional[str]
    spec_tags:List[str] = []
from app.db.enums import ProjectIdentifierStatus, ProjectNameStatus

class ProjectDTO(BaseModel):
    id: str
    raw_name: str
    created_at: datetime

    identifier_status: str
    name_status: str
    is_business_contract_code_verified: bool
    is_name_normalized: bool
    bussiness_editable_info: ProjectBusinessEditableInfo
    @classmethod
    def from_orm_model(cls, project: Project) -> "ProjectDTO":
        return cls(
            id=project.id,
            raw_name=project.raw_name,
            created_at=project.created_at,
            identifier_status=project.identifier_status.value,
            name_status=project.name_status.value,
            is_business_contract_code_verified=(
                project.identifier_status.value == ProjectIdentifierStatus.ok 
            ),
            is_name_normalized=(
                project.name_status.value == ProjectNameStatus.matched
            ),
            bussiness_editable_info=ProjectBusinessEditableInfo(
                business_code=project.business_code,
                contract_code=project.contract_code,
                normalized_name=project.normalized_name,
                spec_tags=project.spec_tags if project.spec_tags else []
            )
        )