from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.models.file_record import FileRecord
from app.services.excel_ingest_service import ExcelIngestService
from app.services.audit_log_service import AuditLogService
from app.agentic.schemas.dto.file_record_dto import FileRecordDTO
from app.db.enums import ParseStatus
from sqlalchemy.orm import Session
from app.services.name_normalization_service import NameNormalizationService
from app.services.file_record_service import FileRecordService
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import sqlite3
from app.agentic.tools.registry import tool_registry


#Part 1 错误分类
def _classify_parse_file_error(e: Exception) -> tuple[ErrorType, str]:
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

    #  系统逻辑冲突，手动文件不用校验
    if "manual" in msg:
        return ErrorType.BUSINESS_RULE_ERROR, msg
    
    #  输入错误，文件类型有误
    if "unsupported" in msg:
        return ErrorType.INPUT_ERROR, msg

    # 兜底：未知异常
    return ErrorType.SYSTEM_ERROR, msg

def parse_file_tool(
    *,
    db: Session,
    file_id: str,
    operator_id: str
) -> ToolResult:

    audit = AuditLogService(db = db)
    name_normalization_service = NameNormalizationService(db=db,
                                                          audit_log_service=audit)
    file_record_service = FileRecordService(db=db, 
                                            audit_log_service=audit)
    ingest_service = ExcelIngestService(db=db, 
                                        audit_log_service=audit,
                                        name_normalization_service=name_normalization_service,
                                        file_service=file_record_service)

    try:
        file = db.get(FileRecord, file_id)
        #检查file是否存在
        if not file:
            return ToolResult(
                ok=False,
                error_type=ErrorType.INPUT_ERROR,
                error_message=f"FileRecord {file_id} not found.",
                explanation="The file does not exist.",
                side_effect=False,
                irreversible=False,
            )
        #检查文件是否被locked。
        if file.locked:
            return ToolResult(
                ok=False,
                error_type=ErrorType.IRREVERSIBLE_CONFLICT,
                error_message="File is locked by CostSummary.",
                explanation="Cannot parse a locked file. Create new file version.",
                side_effect=False,
                irreversible=False,
            )
        #检查是否parse_status == pending
        if file.parse_status != ParseStatus.pending:
            return ToolResult(
                ok=False,
                error_type=ErrorType.BUSINESS_RULE_ERROR,
                error_message="File is not in pending parse state.",
                explanation="File may already be parsed.",
                side_effect=False,
                irreversible=False,
            )
        #调用ingest service进行解析，捕获异常并分类，返回结构化结果
        ingest_service.ingest(file)

        db.commit()
        #返回成功结果，转化成dto
        dto = FileRecordDTO.from_orm_model(file)

        return ToolResult(
            ok=True,
            data=dto.model_dump(),
            explanation="File parsed successfully. Items created. Ready for validation.",
            side_effect=True,
            irreversible=False,
        )

    except Exception as e:
        db.rollback()
        
        et,msg = _classify_parse_file_error(e)

        # 针对不同错误给 LLM 更明确的 next step
        if et == ErrorType.INPUT_ERROR:
            explain = (
                "Cannot parse file because input is invalid (FileType is unsupported for parsing). "
                "Ask the user to re-check inputs and retry."
            )
        elif et == ErrorType.BUSINESS_RULE_ERROR:
            explain = (
                "Cannot parse file because its FileType is manual and manual files cannot be parsed automatically. "
                "Upload a new file with a supported FileType."
            )
        elif et == ErrorType.DATABASE_ERROR:
            explain = (
                "Database error occurred. Retry may work. If repeated, escalate to ERR_ESCALATE with audit details."
            )
        else:
            explain = (
                "Unexpected system error occurred. Retry once; if it fails again, escalate to ERR_ESCALATE."
            )
        return ToolResult(
            ok=False,
            error_type=et,
            error_message=str(e),
            explanation=explain,
            side_effect=False,
            irreversible=False,
        )
        
#Part 3 注册工具，import时自动注册
spec = ToolSpec(
            name="parse_file",
            func=parse_file_tool,
            description="Parse a file",
            input_schema={"db": "Session",
                          "file_id": "str",
                          "operator_id": "str"},
            output_schema= "ToolResult",
            risk_profile=ToolRiskProfile(
                modifies_persistent_data=True,
                irreversible=False,#解析虽然会修改文件记录的状态，但不属于不可逆操作，因为如果不成功，可以重新parse
                deletes_data=False,
                affects_multiple_records=True,#parse一个FileRecord会产生若干的items
                require_human_auth=False
            )
        )

tool_registry.register(spec)