# app/agentic/tools/create_project_tool.py

from sqlalchemy.orm import Session
from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.schemas.dto.project_dto import ProjectDTO
from app.services.project_service import ProjectService
from app.services.audit_log_service import AuditLogService
from app.services.name_normalization_service import NameNormalizationService
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import sqlite3

from app.agentic.tools.registry import tool_registry

#Part 1 错误分类
def _classify_create_project_error(e: Exception) -> tuple[ErrorType, str]:
    # --- 业务/输入类（当前 service 多用 ValueError） ---
    msg = str(e).lower()
    explain_msg = "Unexpected system error. Retry once or escalate."
    # --- DB/系统类 ---
    if isinstance(e, (OperationalError, sqlite3.OperationalError)):
        explain_msg = "Database error occurred while creating project."
        return ErrorType.DATABASE_ERROR, explain_msg
    if isinstance(e, SQLAlchemyError):
        explain_msg = "Database error occurred while creating project."
        return ErrorType.DATABASE_ERROR, explain_msg
    # --- 业务/输入类 ---
    if isinstance(e, ValueError):
        explain_msg = "Invalid input or business rule violation while creating project."
        return ErrorType.BUSINESS_RULE_ERROR, explain_msg
    # 兜底：未知异常
    return ErrorType.SYSTEM_ERROR, explain_msg


def create_project_tool(
    *,
    db: Session,
    raw_name: str,
    business_code: str | None,
    contract_code: str | None,
    spec_tags: list[str] | None,
    operator_id: str
) -> ToolResult:
    #Service 实例化（未来会有重复new service的风险，依赖关系难以测试，未来可以考虑依赖注入框架来管理）
    audit = AuditLogService(db)
    name_normalization_service = NameNormalizationService(db, audit)
    project_service = ProjectService(db, audit, name_normalization_service)

    try:

        # ---- 输入校验 ----
        if not raw_name or raw_name.strip() == "":
            return ToolResult(
                tool_name="create_project_tool",
                ok=False,
                error_type=ErrorType.INPUT_ERROR,
                error_message="raw_name is required.",
                explanation="Project name cannot be empty.",
                side_effect=False,
                irreversible=False,
            )

        # ---- 创建项目 ----
        project = project_service.create_project(
            raw_name=raw_name,
            business_code=business_code,
            contract_code=contract_code,
            spec_tags=spec_tags,
            operator_id=operator_id,
        )

        db.commit()
        db.refresh(project)
        dto = ProjectDTO.from_orm_model(project)

        return ToolResult(
            tool_name="create_project_tool",
            ok=True,
            data=dto.model_dump(),
            explanation=(
                "Project created successfully. "
                "You can now upload files and bind them to this project."
            ),
            side_effect=True,
            irreversible=True,
        )

    except Exception as e:
        db.rollback()
        error_type, explain_msg = _classify_create_project_error(e)
        return ToolResult(
            tool_name="create_project_tool",
            ok=False,
            error_type=error_type,
            error_message=str(e),
            explanation= explain_msg,
            side_effect=False,
            irreversible=False,
        )
    finally:
        db.close()

# ---- ToolSpec 注册 ----

tool_registry.register(ToolSpec(
        name="create_project_tool",
        func=create_project_tool,
        description="Create a new project in the system.",
        input_schema={
            "raw_name": "str",
            "business_code": "str | None",
            "contract_code": "str | None",
            "spec_tags": "list[str] | None",
            "operator_id": "str",
        },
        output_schema="ToolResult",
        risk_profile=ToolRiskProfile(
            modifies_persistent_data=True,
            irreversible=True,
            deletes_data=False,
            affects_multiple_records=False,
            require_human_auth=False,
        ),
    )
)