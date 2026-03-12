# app/agentic/fsm/global_setting.py
# FSM全局配置和常量
from app.agentic.schemas.error_type import ErrorType
from app.agentic.fsm.enums import CostCalcState
RETRYABLE_ERRORS = {
    ErrorType.SYSTEM_ERROR,
    ErrorType.DATABASE_ERROR,
    ErrorType.TIMEOUT_ERROR,
    ErrorType.TOOL_CALL_ERROR,
    ErrorType.SCHEMA_ERROR,
    ErrorType.INPUT_ERROR,
    ErrorType.EXTERNAL_SERVICE_ERROR,
}

FATAL_ERRORS = {
    ErrorType.IRREVERSIBLE_CONFLICT,
    ErrorType.PERMISSION_DENIED,
    ErrorType.BUSINESS_RULE_ERROR,
    ErrorType.VALIDATION_ERROR,
    ErrorType.HUMAN_AUTH_REQUIRED,
    ErrorType.FILE_NOT_FOUND,
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

TOOLALLOWLIST_FOR_EACH_STATE = {
    CostCalcState.S0_INIT: set(),
    CostCalcState.S1_INPUT_GATE: {"extract_project_info_tool","list_raw_uploads_tool","confirm_rawfile_type_tool","bind_validated_file_to_project_tool"},
    CostCalcState.S2_CREATE_PROJECT: {"create_project_tool","create_update_file_record_tool"},
    CostCalcState.S3_PARSE_FILES: {"parse_file_tool"},
    CostCalcState.S4_VALIDATION_CORRECTION_LOOP: {
        "validate_file_tool",
        "batch_edit_items_tool",
        "batch_confirm_items_tool",
        "explain_validation_report_tool",
    },
    CostCalcState.S5_GENERATE_COST_SUMMARY: {"generate_cost_summary_tool"},
    CostCalcState.S6_GENERATE_COST_REPORT: {"generate_cost_report_tool"},
    CostCalcState.S7_PUBLISH_AND_SUMMARIZE: {"cost_report_publish_tool","summarize_experience_tool"},
    CostCalcState.S8_DONE: set(),
    CostCalcState.S_WAIT_USER: {},
    CostCalcState.S_ERR_ESCALATE: {},
}