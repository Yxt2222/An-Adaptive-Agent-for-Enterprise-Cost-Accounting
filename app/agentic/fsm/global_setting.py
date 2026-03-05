# app/agentic/fsm/global_setting.py
# FSM全局配置和常量
from app.agentic.schemas.error_type import ErrorType

RETRYABLE_ERRORS = {
    ErrorType.SYSTEM_ERROR,
    ErrorType.DATABASE_ERROR,
    ErrorType.TIMEOUT_ERROR,
    ErrorType.TOOL_CALL_ERROR,
    ErrorType.SCHEMA_ERROR,
    ErrorType.INPUT_ERROR,
}

FATAL_ERRORS = {
    ErrorType.IRREVERSIBLE_CONFLICT,
    ErrorType.PERMISSION_DENIED,
    ErrorType.BUSINESS_RULE_ERROR,
    ErrorType.VALIDATION_ERROR,
    ErrorType.TOOL_NOT_ALLOWED,
    ErrorType.HUMAN_AUTH_REQUIRED,
}  
 

REQUIRED_FILE_TYPES = {
    "material_cost",
    "part_cost",
    "labor_cost",
    "logistics_cost",
}

VALID_VALIDATION_RESULTS = {"ok","confirmed","blocked","warning"}
RETURN_VALIDATION_REPORT_TOOLS = {
            "validate_file_tool",
            "batch_edit_items_tool",
            "batch_confirm_items_tool"
        }