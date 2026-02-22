from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import sqlite3

from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.dto.cost_summary_dto import CostSummaryDTO

from app.services.cost_calculation_service import CostCalculationService
from app.services.audit_log_service import AuditLogService

from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry

#Part 1 错误分类
def _classify_generate_summary_error(e: Exception) -> tuple[ErrorType, str]:
    """
    把 service 抛出的异常映射为 ErrorType。
    这里先按 service 的异常风格（大量 ValueError）做最小可用分类。
    后续可以把 service 改成更结构化的 DomainError，再更精确。
    """
    # --- 业务/输入类（当前 service 多用 ValueError） ---
    msg = str(e).lower()
    
    # --- DB/系统类 ---
    if isinstance(e, (OperationalError, sqlite3.OperationalError)):
        return ErrorType.DATABASE_ERROR, msg
    if isinstance(e, SQLAlchemyError):
        return ErrorType.DATABASE_ERROR, msg

    # 不可逆冲突：locked / already locked
    if "locked" in msg or "already locked" in msg:
        return ErrorType.IRREVERSIBLE_CONFLICT, msg

    # 校验类：not parsed / not validated
    if "not parsed" in msg or "not validated" in msg:
        return ErrorType.VALIDATION_ERROR, msg

    # 输入类：not found / required / does not belong
    if "not found" in msg or "required" in msg or "does not belong" in msg:
        return ErrorType.INPUT_ERROR, msg

    if "not belong" in msg:
        return ErrorType.TOOL_CALL_ERROR, msg
    # 兜底：未知异常
    return ErrorType.SYSTEM_ERROR, msg

#Part 2 工具实现
def generate_cost_summary_tool(
    *,
    db: Session,
    project_id: str,
    material_file_id: str,
    part_file_id: str,
    labor_file_id: str,
    logistics_file_id: str,
    operator_id: str,
    # 预留：未来你做人类授权 token 或 change_set_id
    human_auth_token: Optional[str] = None,
) -> ToolResult:
    """
    Tool: generate_cost_summary

    Side effects:
    - Creates CostSummary
    - Invalidates old summaries
    - Locks all source FileRecords (irreversible)

    Preconditions:
    - All source FileRecords must be parsed AND validated (ok/confirmed)
    - None of the files are locked
    """

    # 如果未来这个动作需要强制人类授权，可在这里打开
    # if not human_auth_token:
    #     return ToolResult(
    #         ok=False,
    #         error_type=ErrorType.HUMAN_AUTH_REQUIRED,
    #         error_message="Human authorization is required to generate CostSummary.",
    #         explanation="Ask the user to confirm and provide authorization, then retry.",
    #         side_effect=False,
    #         irreversible=False,
    #     )

    audit = AuditLogService(db)
    service = CostCalculationService(db=db, audit_log_service=audit)

    try:
        # 显式事务边界：tool 层负责提交/回滚，executor 不要重复做
        summary = service.generate_cost_summary(
            project_id=project_id,
            material_file_id=material_file_id,
            part_file_id=part_file_id,
            labor_file_id=labor_file_id,
            logistics_file_id=logistics_file_id,
            operator_id=operator_id,
        )
        db.commit()

        dto = CostSummaryDTO.from_domain_model(summary)

        return ToolResult(
            ok=True,
            data=dto.model_dump(),
            explanation=(
                "CostSummary generated successfully. "
                "All source FileRecords are now locked and cannot be modified. "
                "Next step: generate the cost report."
            ),
            side_effect=True,
            irreversible=True,
            audit_ref_id=dto.id,
        )

    except Exception as e:
        db.rollback()

        et,msg = _classify_generate_summary_error(e)

        # 针对不同错误给 LLM 更明确的 next step
        if et == ErrorType.VALIDATION_ERROR:
            explain = (
                "Cannot generate CostSummary because one or more FileRecords are not ready "
                "(not parsed or not validated). Go back to HUMAN_CORRECTION_LOOP or validate step."
            )
        elif et == ErrorType.IRREVERSIBLE_CONFLICT:
            explain = (
                "Cannot generate CostSummary because one or more FileRecords are locked "
                "(already used by a previous CostSummary). Escalate or create a new file version."
            )
        elif et == ErrorType.INPUT_ERROR:
            explain = (
                "Input is invalid (e.g., file_id not found, missing parameters, or file does not belong to project). "
                "Ask the user to re-check inputs and retry."
            )
        elif et == ErrorType.DATABASE_ERROR:
            explain = (
                "Database error occurred. Retry may work. If repeated, escalate to ERR_ESCALATE with audit details."
            )
        elif et == ErrorType.TOOL_CALL_ERROR:
            explain = (
                "Tool call error due to invalid parameters in tool call(not schema fail). Check the error message for details "
                "and try again. Error message: " + msg
            )
        else:
            explain = (
                "Unexpected system error occurred. Retry once; if it fails again, escalate to ERR_ESCALATE."
            )

        return ToolResult(
            ok=False,
            error_type=et,
            error_message=str(e),
            data=None,
            explanation=explain,
            side_effect=False,
            irreversible=False,
            audit_ref_id=None,
        )
#Part 3 注册工具，import时自动注册
spec = ToolSpec(
            name="generate_cost_summary",
            func=generate_cost_summary_tool,
            description="Generate cost summary",
            input_schema={"db": "Session",
                          "project_id": "str",
                          "material_file_id": "str",
                          "part_file_id": "str",
                          "labor_file_id": "str",
                          "logistics_file_id": "str",
                          "operator_id": "str"},
            output_schema= "ToolResult",
            risk_profile=ToolRiskProfile(
                modifies_persistent_data=True,
                irreversible=True,
                deletes_data=False,
                affects_multiple_records=True,
                require_human_auth=True
            )
        )

tool_registry.register(spec)