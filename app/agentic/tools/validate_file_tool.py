from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.dto.validate_report_dto import ValidationReportDTO
from app.services.validation_service import ValidationService
from app.services.audit_log_service import AuditLogService
from app.models.file_record import FileRecord
from sqlalchemy.orm import Session

from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry
from app.db.enums import ParseStatus, ValidationStatus


def validate_file_tool(
    *,
    db: Session,
    file_id: str,
    operator_id: str
) -> ToolResult:
    audit = AuditLogService(db)
    service = ValidationService(db=db, audit_log_service=audit)
    #尝试检索文件记录，检查状态，调用 service 验证，捕获异常并分类，返回结构化结果
    try:
        file = db.get(FileRecord, file_id)
        #检查file是否存在
        if not file:
            return ToolResult(
                ok=False,
                error_type=ErrorType.INPUT_ERROR,
                error_message=f"FileRecord {file_id} not found.",
                data = None,
                explanation="The file does not exist. Ask user to re-upload.",
                side_effect=False,
                irreversible=False,
                audit_ref_id=None,
            )
        #检查parse_status == parsed
        if file.parse_status != ParseStatus.parsed:
            return ToolResult(
                ok=False,
                error_type=ErrorType.BUSINESS_RULE_ERROR,
                error_message="File must be parsed before validation.",
                data = None,
                explanation="Run parse_file_tool before validation.",
                side_effect=False,
                irreversible=False,
                audit_ref_id=None,
            )
        #检查validation_status ==pending
        if file.validation_status != ValidationStatus.pending:
            return ToolResult(
                ok=False,
                error_type=ErrorType.BUSINESS_RULE_ERROR,
                error_message="File is not in pending validation state.",
                data = None,
                explanation="File may already be validated.",
                side_effect=False,
                irreversible=False,
                audit_ref_id=None,
            )
        #调用validation_service.validate_file()
        report = service.validate_file(file)

        db.commit()
        #将ValidationReport转换成DTO
        dto = ValidationReportDTO.from_domain_model(report)
        #返回tool result
        return ToolResult(
            ok=True,
            data=dto.model_dump(),
            explanation=(
                f"Validation completed. "
                f"Total: {dto.summary.total_items}, "
                f"Blocked:{dto.summary.blocked_count}, "
                f"Warning:{dto.summary.warning_count}. "
                "If blocked > 0 → enter HUMAN_CORRECTION_LOOP."
            ),
            side_effect=True,
            irreversible=False
        )
    #分类错误，Validate_file的错误没那么复杂
    except Exception as e:
        db.rollback()
        return ToolResult(
            ok=False,
            error_type=ErrorType.DATABASE_ERROR,
            error_message=str(e),
            data=None,
            explanation="Database error occurred during validation.",
            side_effect=False,
            irreversible=False,
            audit_ref_id=None,
        )

#Part 3 注册工具，import时自动注册
spec = ToolSpec(
            name="validate_file",
            func=validate_file_tool,
            description="Validate a file",
            input_schema={"db": "Session",
                          "file_id": "str",
                          "operator_id": "str"},
            output_schema= "ToolResult",
            risk_profile=ToolRiskProfile(
                modifies_persistent_data=True,
                irreversible=False,#验证虽然会修改文件记录的状态，但不属于不可逆操作，因为可以重新修改item，然后revalidate
                deletes_data=False,
                affects_multiple_records=True,#同时产生多个items对象，属于多记录修改
                require_human_auth=False
            )
        )

tool_registry.register(spec)