# app/agentic/tools/create_update_file_record_tool.py

import os
import hashlib
import sqlite3
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from app.models.project import Project
from app.models.file_record import FileRecord
from app.db.enums import FileType
from app.services.file_record_service import FileRecordService
from app.services.audit_log_service import AuditLogService

from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.schemas.dto.file_record_dto import FileRecordDTO

from app.agentic.tools.registry import tool_registry


def _classify_error(e: Exception):
    explain_msg = "Unexpected system error. Retry once or escalate."
    if isinstance(e, (OperationalError, sqlite3.OperationalError, SQLAlchemyError)):
        explain_msg = "Database error occurred."
        return ErrorType.DATABASE_ERROR, explain_msg
    if isinstance(e, ValueError):
        explain_msg = f"business rule violation: {e}"
        return ErrorType.BUSINESS_RULE_ERROR, explain_msg
    return ErrorType.SYSTEM_ERROR, explain_msg


def create_update_file_record_tool(
    *,
    db: Session,
    project_id: str,
    file_type: str,
    storage_path: str,
    original_name: str,
    operator_id: str
) -> ToolResult:
    '''
    现在系统存在一个隐患,Tool 接收 storage_path,这意味着 LLM 可以直接指定路径.未来改为： 
    Web 上传 → 生成 upload_token -> Tool 接收upload_token -> Tool 内部解析真实路径
    '''
    ft_dict = {"material": FileType.material_cost,
               "part": FileType.part_cost,
               "labor": FileType.labor_cost,
               "logistics": FileType.logistics_cost}
    audit = AuditLogService(db)
    file_service = FileRecordService(db, audit)

    try:

        # ---- project must exist ----
        project = db.get(Project, project_id)
        if not project:
            return ToolResult(
                tool_name="create_update_file_record_tool",
                ok=False,
                error_type=ErrorType.INPUT_ERROR,
                error_message="Project not found.",
                explanation="The specified project does not exist.",
                side_effect=False,
                irreversible=False,
            )

        # ---- file must exist ----
        if not os.path.exists(storage_path):
            return ToolResult(
                tool_name="create_update_file_record_tool",
                ok=False,
                error_type=ErrorType.INPUT_ERROR,
                error_message="File does not exist on server.",
                explanation="File must be uploaded before binding.",
                side_effect=False,
                irreversible=False,
            )
        # -------- 安全检查：storage_path必须在允许的上传目录下，防止越界访问 --------
        '''
        UPLOAD_ROOT = os.path.abspath("uploads")
        abs_path = os.path.abspath(storage_path)
        if not abs_path.startswith(UPLOAD_ROOT):
            return ToolResult(
                tool_name="create_update_file_record_tool",
                ok=False,
                error_type=ErrorType.PERMISSION_DENIED,
                error_message="Invalid file path.",
                explanation="File must be inside uploads directory.",
                side_effect=False,
                irreversible=False,
            )
        '''
        # ---- compute hash ----
        with open(storage_path, "rb") as f:
            file_bytes = f.read()  

        # ---- enum validation ----
        try:
            file_type_enum = ft_dict[file_type.lower()]
        except Exception:
            return ToolResult(
                tool_name="create_update_file_record_tool",
                ok=False,
                error_type=ErrorType.INPUT_ERROR,
                error_message="Invalid file type.",
                explanation=f"FileType must be one of these str: {list(ft_dict.keys())}",
                side_effect=False,
                irreversible=False,
            )

        # ---- create or update ----
        file_record = file_service.create_update_file_record(
            project_id=project_id,
            file_type=file_type_enum,
            original_name=original_name,
            storage_path=storage_path,
            file_bytes=file_bytes,
            operator_id=operator_id,
        )

        db.commit()
        db.refresh(file_record)

        dto = FileRecordDTO.from_orm_model(file_record)

        return ToolResult(
            tool_name="create_update_file_record_tool",
            ok=True,
            data=dto.model_dump(),
            explanation=(
                "File successfully bound to project. "
                "Next step: if haven't uploaded other files, continue to upload other files. Otherwise, run parse_file_tool to parse uploaded file."
            ),
            side_effect=True,
            irreversible=False,
        )

    except Exception as e:
        db.rollback()
        error_type, explanation = _classify_error(e)

        return ToolResult(
            tool_name="create_update_file_record_tool",
            ok=False,
            error_type=error_type,
            error_message=str(e),
            explanation=explanation,
            side_effect=False,
            irreversible=False,
        )
    finally:
        db.close()


# ---- ToolSpec ----

tool_registry.register(ToolSpec(
        name="create_update_file_record_tool",
        func=create_update_file_record_tool,
        description="Bind or update a file for a project.",
        input_schema={
            "project_id": "str",
            "file_type": "str",
            "storage_path": "str",
            "original_name": "str",
            "operator_id": "str",
        },
        output_schema="ToolResult",
        risk_profile=ToolRiskProfile(
            modifies_persistent_data=True,
            irreversible=False,
            deletes_data=False,
            affects_multiple_records=False,
            require_human_auth=False,
        ),
    )
)