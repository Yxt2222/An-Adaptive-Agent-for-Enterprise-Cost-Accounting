import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import sqlite3

from app.agentic.schemas.dto.cost_report_file_dto import CostReportFileDTO
from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.dto.cost_summary_dto import CostSummaryDTO

from app.models.cost_summary import CostSummary
from app.services.cost_calculation_service import CostCalculationService
from app.services.audit_log_service import AuditLogService

from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry
from app.services.cost_report_service import CostReportService

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



# ===============================
# 工具实现
# ===============================
def generate_cost_report_tool(
    *,
    db: Session,
    cost_summary_id: str,
    operator_id: str,
) -> ToolResult:
    """
    Tool: generate_cost_report_tool
    
    Side effects:
    - Generates Excel cost report file
    - Updates CostSummary report fields (report_file_name, report_storage_path, report_generated_at)
    - Creates audit log entry
    
    Preconditions:
    - CostSummary with cost_summary_id must exist
    - CostSummary status must be ACTIVE
    
    Returns:
        CostReportFileDTO with metadata for frontend download
    """
    # 初始化Service层
    audit = AuditLogService(db)
    cost_calculation_service = CostCalculationService(db=db, audit_log_service=audit)
    cost_report_service = CostReportService(
        db=db,
        audit_log_service=audit,
        cost_calculation_service=cost_calculation_service,
    )

    try:
        # 委托给Service层处理所有业务逻辑
        report_data = cost_report_service.generate_report(
            cost_summary_id=cost_summary_id,
            operator_id=operator_id,
        )

        db.commit()

        # 构造DTO返回
        dto = CostReportFileDTO(
            cost_summary_id=report_data["cost_summary_id"],
            project_id=report_data["project_id"],
            calculation_version=report_data["calculation_version"],
            file_name=report_data["file_name"],
            storage_path=report_data["storage_path"],
            mime_type=report_data["mime_type"],
            generated_at=report_data["generated_at"],
            download_url=report_data["download_url"],
        )

        return ToolResult(
            tool_name="generate_cost_report_tool",
            ok=True,
            data=dto.model_dump(mode="json"),
            explanation=(
                "Cost report Excel generated successfully. "
                f"File: {dto.file_name}. "
                "Ready for frontend download."
            ),
            side_effect=True,
            irreversible=False,
            audit_ref_id=report_data["cost_summary_id"],
        )

    except Exception as e:
        db.rollback()
        error_type, error_message, explanation = _classify_generate_report_error(e)
        
        return ToolResult(
            tool_name="generate_cost_report_tool",
            ok=False,
            error_type=error_type,
            error_message=error_message,
            data=None,
            explanation=explanation,
            side_effect=False,
            irreversible=False,
            audit_ref_id=None,
        )


# ===============================
# ToolSpec 注册
# ===============================
tool_registry.register(
    ToolSpec(
        name="generate_cost_report_tool",
        func=generate_cost_report_tool,
        description=(
            "Generate an Excel cost report from an existing active CostSummary. "
            "The report includes project info, material costs, part costs, "
            "labor costs, and logistics costs with human-readable formatting. "
            "Updates CostSummary with report metadata and returns "
            "download-oriented file metadata for frontend delivery."
        ),
        input_schema={
            "cost_summary_id": "str",
            "operator_id": "str",
        },
        output_schema={
            "tool_name": "str",
            "ok": "bool",
            "error_type": "Optional[ErrorType]",
            "error_name": "Optional[str]",
            "data": {
                "cost_summary_id": "str",
                "project_id": "str",
                "calculation_version": "int",
                "file_name": "str",
                "storage_path": "str",
                "mime_type": "str",
                "generated_at": "str",
                "download_url": "str",
            },
            "explanation": "Optional[str]",
            "side_effect": "bool",
            "irreversible": "bool",
            "audit_ref_id": "Optional[str]",
        },
        risk_profile=ToolRiskProfile(
            modifies_persistent_data=True,  # 更新CostSummary字段
            irreversible=False,
            deletes_data=False,
            affects_multiple_records=False,  # 只更新一个CostSummary
            require_human_auth=False,
        ),
    )
)