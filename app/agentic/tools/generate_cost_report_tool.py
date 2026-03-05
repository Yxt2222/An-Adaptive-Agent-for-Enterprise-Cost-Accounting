from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import sqlite3

from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.dto.cost_summary_dto import CostSummaryDTO

from app.models.cost_summary import CostSummary
from app.services.cost_calculation_service import CostCalculationService
from app.services.audit_log_service import AuditLogService

from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry

#Part 1 错误分类
def _classify_generate_report_error(e: Exception) -> tuple[ErrorType, str, str]:
    """
    把 service 抛出的异常映射为 ErrorType。
    这里先按 service 的异常风格（大量 ValueError）做最小可用分类。
    后续可以把 service 改成更结构化的 DomainError，再更精确。
    """
    # --- 业务/输入类（当前 service 多用 ValueError） ---
    msg = str(e).lower()
    
    # --- DB/系统类 ---
    if isinstance(e, (OperationalError, sqlite3.OperationalError)):
        explain = (
                "Database error occurred. Retry may work. If repeated, escalate to ERR_ESCALATE with audit details."
            )
        return ErrorType.DATABASE_ERROR, msg, explain
    if isinstance(e, SQLAlchemyError):
        explain = (
                "Database error occurred. Retry may work. If repeated, escalate to ERR_ESCALATE with audit details."
            )
        return ErrorType.DATABASE_ERROR, msg, explain
    if "active" in msg:
        explain = "business rule violation."  
        return ErrorType.BUSINESS_RULE_ERROR, msg, explain
    
    if "not found" in msg:
        explain = (
                "Input is invalid (e.g., file_id not found). Check the error message for details and try again."
            )
        return ErrorType.INPUT_ERROR, msg, explain

    if "not belong" in msg:
        explain = (
                "Tool call error due to invalid parameters in tool call(not schema fail). Check the error message for details "
                "and try again. Error message: " + msg
            )
        return ErrorType.TOOL_CALL_ERROR, msg, explain
    # 兜底：未知异常
    explain = (
                "Unexpected system error occurred. Retry once; if it fails again, escalate to ERR_ESCALATE."
            )
    return ErrorType.SYSTEM_ERROR, msg, explain

#Part 2 工具实现
def generate_cost_report_tool(
    *,
    db: Session,
    cost_summary_id: str,
    operator_id: str,
) -> ToolResult:
    """
    Tool: generate_cost_summary_report

    Preconditions:
    - CostSummary with cost_summary_id already exists (created in S5).
    """

    audit = AuditLogService(db)
    service = CostCalculationService(db=db, audit_log_service=audit)
    cost_summary = db.get(CostSummary, cost_summary_id)
    
    if not cost_summary:
        return ToolResult(
            tool_name="generate_cost_summary_tool",
            ok=False,
            error_type=ErrorType.INPUT_ERROR,
            error_message=f"CostSummary with id {cost_summary_id} not found.",
            data=None,
            explanation="The specified CostSummary does not exist. Please check the cost_summary_id and try again.",
            side_effect=False,
            irreversible=False,
            audit_ref_id=None,
        )
        
    try:
        # 显式事务边界：tool 层负责提交/回滚，executor 不要重复做
        df_report = service.generate_df_report(
            cost_summary=cost_summary,
            operator_id=operator_id,
        )
 

        return ToolResult(
            tool_name="generate_cost_summary_tool",
            ok=True,
            data=df_report,#todo
            explanation=(
                "cost_summary report generated successfully. "
            ),
            side_effect=False,
            irreversible=True,
        )

    except Exception as e:
        db.rollback()
        et,msg,explain =_classify_generate_report_error(e)
        return ToolResult(
            tool_name="generate_cost_summary_tool",
            ok=False,
            error_type=et,
            error_message=str(e),
            data=None,
            explanation=explain,
            side_effect=False,
            irreversible=False,
            audit_ref_id=None,
        )
    finally:
        db.close()
#Part 3 注册工具，import时自动注册
tool_registry.register(ToolSpec(
            name="generate_cost_report_tool",
            func=generate_cost_report_tool,
            description="Generate cost report",
            input_schema={"cost_summary_id":"str",                     
                          "operator_id": "str"},
            output_schema= "ToolResult",
            risk_profile=ToolRiskProfile(
                modifies_persistent_data=False,
                irreversible=False,               
                deletes_data=False,
                affects_multiple_records=False,
                require_human_auth=False
            )
        )
    )
 