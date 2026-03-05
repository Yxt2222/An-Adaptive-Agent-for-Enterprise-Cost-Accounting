import shutil
import os
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.agentic.schemas.dto.file_record_dto import FileRecordDTO
from app.models.raw_upload_record import RawUploadRecord, RawUploadStatus
from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType
from app.services.file_record_service import FileRecordService
from app.services.audit_log_service import AuditLogService
from app.db.enums import FileType

from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry

def bind_validated_file_to_project_tool(
    *,
    db: Session,
    raw_upload_id: str,
    project_id: str,
    operator_id: str,
    agent_run_id: str,
) -> ToolResult:
    '''
    绑定经过验证的上传文件到项目，生成 FileRecord，并把文件移动到正式目录。
    
    raw_upload_id: 已经上传并验证的 RawUploadRecord 的 ID
    project_id: 目标项目 ID
    file_type: 文件类型，material/labor/logistics/part
    operator_id: 操作者 ID，用于审计日志
    '''
    filetype_list = [
        FileType.material_cost,
        FileType.labor_cost,
        FileType.logistics_cost,
        FileType.part_cost,
    ]

    try:

        raw = db.query(RawUploadRecord)\
            .filter(RawUploadRecord.id == raw_upload_id)\
            .with_for_update()\
            .first()
        #空值校验
        if not raw:
            return ToolResult(
                tool_name="bind_validated_file_to_project_tool",
                ok=False,
                error_type=ErrorType.INPUT_ERROR,
                error_message="Raw upload not found."
            )
        #会话一致性校验   
        if raw.agent_run_id != agent_run_id:
            return ToolResult(
                tool_name="bind_validated_file_to_project_tool",
                ok=False,
                error_type=ErrorType.BUSINESS_RULE_ERROR,
                error_message=f"RawUploadRecord with id {raw_upload_id} does not belong to agent_run_id {agent_run_id}.Cross-run operation forbidden."
            )
        #文件类型校验
        if raw.file_type not in filetype_list:
            return ToolResult(
                tool_name="bind_validated_file_to_project_tool",
                ok=False,
                error_type=ErrorType.BUSINESS_RULE_ERROR,
                error_message=f"RawUploadRecord with id {raw_upload_id} is not in probed status. File type is not in allowed list."
            )   
        #状态校验
        if raw.status != RawUploadStatus.confirmed:
            return ToolResult(
                tool_name="bind_validated_file_to_project_tool",
                ok=False,
                error_type=ErrorType.VALIDATION_ERROR,
                error_message=f"Raw upload with id {raw_upload_id} not confirmed. Only confirmed raw uploads can be bound to a project."
            )

        # 先创建 file_record 再决定路径名（推荐用 version）
        audit = AuditLogService(db)
        file_service = FileRecordService(db, audit_log_service=audit)
        # 计算下一个版本号，确保文件命名的唯一性和连续性
        next_version = file_service.get_latest_version(project_id=project_id, file_type=raw.file_type) + 1
        # 构建最终文件路径
        project_dir = f"./uploads/projects/{project_id}"
        os.makedirs(project_dir, exist_ok=True)
        final_path = os.path.join(
            project_dir,
            f"{raw.file_type.value}_v{next_version}.xlsx"
        )

        # 先 move
        shutil.move(raw.storage_path, final_path)
        
        # 提起最终归档路径的文件字节，创建FileRecord时给file_bytes参数，确保service层可以选择性地进行hash校验
        with open(final_path, "rb") as f:
            file_bytes = f.read()

        # 创建 FileRecord（让 service 决定 version）
        file_record = file_service.create_update_file_record(
            project_id=project_id,
            file_type=raw.file_type,
            storage_path=final_path,
            operator_id=operator_id,
            original_name=raw.original_filename,
            file_bytes=file_bytes,  # 如果你未来想校验hash，可以再优化
        )

        raw.status = RawUploadStatus.bound
        raw.storage_path = final_path

        db.commit()

        dto = FileRecordDTO.from_orm_model(file_record)
        return ToolResult(
            tool_name="bind_validated_file_to_project_tool",
            ok=True,
            data=dto.model_dump(),
            explanation="File successfully bound to project.",
            side_effect=True,
            irreversible=False,
        )

    except Exception as e:
        db.rollback()
        return ToolResult(
            tool_name="bind_validated_file_to_project_tool",
            ok=False,
            error_type=ErrorType.SYSTEM_ERROR,
            error_message=str(e),
        )
    finally:
        db.close()
        
# ---- ToolSpec 注册 ----

tool_registry.register(ToolSpec(
        name="bind_validated_file_to_project_tool",
        func=bind_validated_file_to_project_tool,
        description="Bind a validated file to a project.",
        input_schema={
            "raw_upload_id": "str",
            "project_id": "str",
            "file_type": "str",
            "operator_id": "str",
        },
        output_schema="ToolResult",
        risk_profile=ToolRiskProfile(
            modifies_persistent_data=True,
            irreversible=True,#FileRecord不允许删除，但是可以被覆盖
            deletes_data=False,
            affects_multiple_records=True,#既会产生FileRecord,也会更改RawUploadRecord的地址
            require_human_auth=True,
        ),
    )
)