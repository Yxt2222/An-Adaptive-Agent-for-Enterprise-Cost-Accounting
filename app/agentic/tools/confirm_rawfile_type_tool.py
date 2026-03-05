from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import sqlite3

from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType

from app.services.audit_log_service import AuditLogService
from app.services.raw_file_record_service import RawUploadRecordService

from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry

def _classify_confirm_error(e: Exception) -> tuple[ErrorType, str, str]:
    msg = str(e)
    lower_msg = msg.lower()

    if isinstance(e, (OperationalError, sqlite3.OperationalError, SQLAlchemyError)):
        return (
            ErrorType.DATABASE_ERROR,
            msg,
            "Unexpected database error. Retry once or escalate."
        )

    if isinstance(e, ValueError):
        if "not found" in lower_msg :
            return (
                ErrorType.INPUT_ERROR,
                msg,
                "The specified raw upload record was not found. Please check the raw_upload_id and try again."
            )
        if "cross-run operation" in lower_msg:
            return (
                ErrorType.INPUT_ERROR,
                msg,
                "The raw upload record does not belong to the current agent run. Cross-run operations are not allowed.Please check the raw_upload_id and try again."
            )
        if "not in probed status" in lower_msg:
            return (
                ErrorType.BUSINESS_RULE_ERROR,
                msg,
                "Only raw upload records in 'probed' status can be confirmed. Check the raw_upload_id and select another qualified rawfile."
            )
        if "file type" in lower_msg:
            return (
                ErrorType.BUSINESS_RULE_ERROR,
                msg,
                "The raw upload record does not have a successfully probed file type and cannot be confirmed. Check the raw_upload_id and select another qualified rawfile."
            )
        
    return (
        ErrorType.SYSTEM_ERROR,
        msg,
        "Unexpected system error. Retry once or escalate."
    )


def confirm_raw_upload_tool(
    *,
    db: Session,
    agent_run_id: str,
    raw_upload_id: str,
    operator_id: str,
) -> ToolResult:
    
    try:
        audit = AuditLogService(db)
        raw_service = RawUploadRecordService(db, audit)
        raw_file_record = raw_service.get_by_id(raw_upload_id)
        if not raw_file_record:
            return ToolResult(
                tool_name="confirm_raw_upload_tool",
                ok=False,
                error_type=ErrorType.INPUT_ERROR,
                error_message="Raw upload record not found.",
                explanation="raw_upload_id is wrong. Please check the raw_upload_id and try again.",
            )
        raw_service.confirm_file_type(
            agent_run_id=agent_run_id,
            raw_upload_id=raw_upload_id,
            operator_id=operator_id,
        )

        db.commit()

        return ToolResult(
            tool_name="confirm_raw_upload_tool",
            ok=True,
            data={
                "raw_upload_id": raw_upload_id,
                "confirmed_file_type": raw_file_record.file_type.value if raw_file_record.file_type else None,
                "new_status": "confirmed",
            },
            explanation="Raw upload successfully confirmed.",
            side_effect=True,
            irreversible=True,
        )

    except Exception as e:
        db.rollback()
        error_type, error_message, explanation = _classify_confirm_error(e)
        return ToolResult(
            tool_name="confirm_raw_upload_tool",
            ok=False,
            error_type=error_type,
            error_message=error_message,
            explanation=explanation,
        )
    finally:
        db.close()

# ---- ToolSpec 注册 ----

tool_registry.register(ToolSpec(
        name="confirm_raw_upload_tool",
        func=confirm_raw_upload_tool,
        description="Confirm a probed raw upload after human authorization.",
        input_schema={
            "agent_run_id": "str",
            "raw_upload_id": "str",
            "operator_id": "str",
        },
        output_schema="ToolResult",
        risk_profile=ToolRiskProfile(
            modifies_persistent_data=True,
            irreversible=True,                  # confirmed 是单向状态
            deletes_data=False,
            affects_multiple_records=False,
            require_human_auth=True,            # 必须人工确认
        ),
    )
)