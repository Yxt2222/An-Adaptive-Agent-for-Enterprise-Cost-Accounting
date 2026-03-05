from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType

from app.services.audit_log_service import AuditLogService
from app.services.item_edit_service import ItemEditService
from app.services.validation_service import ValidationReport, ValidationService

from app.agentic.schemas.dto.validate_report_dto import ValidationReportDTO
from app.models.batchEditItemsInput import BatchEditItemsInput 
from app.db.session import get_session

import sqlite3
from sqlalchemy.exc import SQLAlchemyError, OperationalError     
from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry


#Part 1 错误分类
def _classify_batch_edit_items_error(e: Exception) -> tuple[ErrorType, str, str]:
    # --- 业务/输入类（当前 service 多用 ValueError） ---
    msg = str(e).lower()
    explain_msg = "Unexpected system error. Retry once or escalate."
    # --- DB/系统类 ---sqlite3.OperationalError
    if isinstance(e, (OperationalError, sqlite3.OperationalError)):
        explain_msg = "Database error occurred while creating project."
        return ErrorType.DATABASE_ERROR, explain_msg, msg
    if isinstance(e, SQLAlchemyError):
        explain_msg = "Database error occurred while creating project."
        return ErrorType.DATABASE_ERROR, explain_msg, msg
    if isinstance(e, RuntimeError):
        explain_msg = "Business rule violation"
        return ErrorType.BUSINESS_RULE_ERROR, explain_msg,msg
    
    # --- 业务/输入类 ---
    if "length" in msg or "empty" in msg:
        explain_msg = "quantity of the input data is incorrect. Please check the input lists and try again."
        return ErrorType.INPUT_ERROR, explain_msg,msg
    if "source" in msg and "file" in msg:
        explain_msg = "source_file related issue happened. Please check if all the input items have a correct source_file_id."
        return ErrorType.VALIDATION_ERROR, explain_msg,msg
    if isinstance(e, ValueError):
        explain_msg = "Invalid input or business rule violation while creating project."
        return ErrorType.BUSINESS_RULE_ERROR, explain_msg,msg
    # 兜底：未知异常
    return ErrorType.SYSTEM_ERROR, explain_msg,msg

# Part 2 Tool 实现
def batch_edit_items_tool(args: dict) -> ToolResult:
    try:

        input_dto = BatchEditItemsInput(**args)

    except Exception as e:

        return ToolResult(
            ok=False,
            tool_name="batch_edit_items_tool",
            error_type=ErrorType.INPUT_ERROR,
            error_message=str(e),
        )

    db = get_session()

    try:
        audit = AuditLogService(db)
        validation_service=ValidationService(db, audit)
        service = ItemEditService(db, audit_log_service=audit, validation_service=validation_service)

        result = service.batch_edit_items(
            item_type_lst=input_dto.item_type_lst,
            item_id_lst=input_dto.item_id_lst,
            updates_lst=input_dto.updates_lst,
            operator_id=input_dto.operator_id
        )

        # --------------------------
        # 获取 source_file_id
        # --------------------------

    

        db.commit()
        
        if isinstance(result, ValidationReport):
            report_dto = ValidationReportDTO.from_domain_model(result)
            return ToolResult(
            ok=True,
            tool_name="batch_edit_items_tool",
            data=report_dto.model_dump(),
            explanation=f"Batch edit completed with validation triggered. Validation report included in the output.",
        )
        else:
            return ToolResult(
                ok=True,
                tool_name="batch_edit_items_tool",
                data=None,
                explanation=f"No data needed to be changed, No validation triggered.",
            )
  

      

    except Exception as e:
        db.rollback()
        error_type,explanation,msg = _classify_batch_edit_items_error(e)
        return ToolResult( 
            ok=False,
            tool_name="batch_edit_items_tool",
            error_type=error_type,
            error_message=msg,
            explanation=explanation,
            side_effect=False,
            irreversible=False,
        )
    finally:
        db.close()

# Part 3 ToolSpec 注册
tool_registry.register(ToolSpec(
    name="batch_edit_items_tool",
    func=batch_edit_items_tool,
    description="""Batch edit validation issues and trigger file validation.
    Used in S4/S5 validation correction loop.
    All items must belong to the same file.
    """,
    input_schema={"_request_id": "str | None",
    "item_type_lst": "List[str]",
    "item_id_lst": "List[str]",
    "updates_lst": "List[Dict[str, Any]]",
    "operator_id": "str"},
    output_schema="ToolResult",
    risk_profile=ToolRiskProfile(
        modifies_persistent_data=True,
        irreversible=False,#FileRecord不允许删除，但是可以被覆盖
        deletes_data=False,
        affects_multiple_records=True,#既会产生FileRecord,也会更改RawUploadRecord的地址
        require_human_auth=True,
    ),
))