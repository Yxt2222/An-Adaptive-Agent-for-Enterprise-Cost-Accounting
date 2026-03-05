import sqlite3
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.models.raw_upload_record import RawUploadRecord
from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType

from app.services.audit_log_service import AuditLogService
from app.services.raw_file_record_service import RawUploadRecordService
from app.db.enums import RawUploadStatus, FileType

from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry

#Part 1 错误分类
def _classify_list_rawuploads_error(e: Exception) -> tuple[ErrorType, str,str]:
    """
    把 service 抛出的异常映射为 ErrorType。
    这里先按 service 的异常风格（大量 ValueError）做最小可用分类。
    后续可以把 service 改成更结构化的 DomainError，再更精确。
    """
    # --- 业务/输入类（当前 service 多用 ValueError） ---
    msg = str(e).lower()
    # --- DB/系统类 ---
    explanation = "Unexpected system error. Retry once or escalate."
    if isinstance(e, (OperationalError, sqlite3.OperationalError, SQLAlchemyError)):
        return ErrorType.DATABASE_ERROR, msg, explanation
    
    # 输入类：Invalid file_type
    if "invalid file_type" in msg:
        explanation = "The file_type parameter must be one of the allowed values."
        return ErrorType.INPUT_ERROR, msg, explanation
    # 输入类：Invalid status
    if "invalid status" in msg:
        explanation = "The status parameter must be one of the allowed values."
        return ErrorType.INPUT_ERROR, msg, explanation
    # 兜底：未知异常
    explanation = "Unexpected system error. Retry once or escalate."
    return ErrorType.SYSTEM_ERROR, msg, explanation

def list_raw_uploads_tool(
    *,
    db: Session,
    agent_run_id: str,
    file_type: str | None = None,
    status: str | None = None,
) -> ToolResult:      
    #空值校验：agent_run_id是必须的
    if not agent_run_id:
        return ToolResult(
            tool_name="list_raw_uploads_tool",
            ok=False,
            error_type=ErrorType.INPUT_ERROR,
            error_message="agent_run_id is required.",
            explanation="The agent_run_id parameter is required and cannot be empty.",
        )
    audit = AuditLogService(db)
    raw_upload_service = RawUploadRecordService(db, audit)
    try:
        records: List[RawUploadRecord] = raw_upload_service.list_by_run(agent_run_id=agent_run_id, 
                                                                        file_type=file_type, 
                                                                        status=status)
        data = [
            {
                "raw_upload_id": r.id,
                "agent_run_id": r.agent_run_id,
                "original_filename": r.original_filename,
                "storage_path": r.storage_path,
                "upload_time": r.upload_time.isoformat(),
                "file_type": r.file_type.value if r.file_type else None,
                "version": r.version,
                "file_hash": r.file_hash,
                "size": r.size,
                "status": r.status.value,
                "detected_columns": r.detected_columns,
                "probe_error": r.probe_error,
            }
            for r in records
        ]

        return ToolResult(
            tool_name="list_raw_uploads_tool",
            ok=True,
            data={"uploads": data},
            explanation="Raw uploads retrieved successfully.",
            side_effect=False,
            irreversible=False,
        )

    except Exception as e:
        error_type, error_message, explanation = _classify_list_rawuploads_error(e)
        return ToolResult(
            tool_name="list_raw_uploads_tool",
            ok=False,
            error_type=error_type,
            error_message=error_message,
            explanation=explanation,
        )
    finally:
        db.close()
        
#Part 3 注册工具，import时自动注册
tool_registry.register(ToolSpec(
            name="list_raw_uploads_tool",
            func=list_raw_uploads_tool,
            description="List raw uploads for an agent run",
            input_schema={"agent_run_id": "str",
                          "file_type": "str | None",
                          "status": "str | None"},
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