from enum import Enum

class ErrorType(str, Enum):
    '''
    执行过程中可能出现的问题的结构化分类与表达
    
    参数	说明
    INPUT_ERROR:用户输入不符合要求或者语义有误。FSM回到WAIT_USER,请求重输入.
    VALIDATION_ERROR:数据状态未满足当前业务状态要求。FSM回到HUMAN_CORRECTION_LOOP。
    BUSINESS_RULE_ERROR:操作违反了领域业务规则
    PERMISSION_DENIED:当前用户或会话无权限执行该操作,FSM回WAIT_USER，并提示权限不足。
    HUMAN_AUTH_REQUIRED:该操作需要人工授权，但当前调用未携带授权证明。
    SCHEMA_ERROR:调用tool时，LLM生成的toolcall不满足tool的input_schema要求。
    TOOL_CALL_ERROR:FSM在生成toolcall时，传参有误（非schema不匹配）。返回报错信息，FSM自动重试，超过最大重试次数后->ERR_ESCALATE
    TOOL_NOT_ALLOWED:当前 FSM 状态不允许调用该 tool。
    SYSTEM_ERROR:未知异常或未分类异常。重试，超过最大重试次数后->ERR_ESCALATE
    DATABASE_ERROR:数据库操作失败，例如实体不存在，事务冲突，连接失败，约束冲突等等。
    TIME_OUT_ERROR:外部调用或 DB 查询超时。FSM自动重试，超过最大重试次数后->ERR_ESCALATE
    IRREVERSIBLE_CONFLICT:尝试执行的操作与不可逆状态冲突。结构性冲突，没有重试必要，直接->ERR_ESCALATE

    '''
    # 输入问题
    INPUT_ERROR = "INPUT_ERROR"

    # 业务规则问题
    VALIDATION_ERROR = "VALIDATION_ERROR"
    BUSINESS_RULE_ERROR = "BUSINESS_RULE_ERROR"

    # 权限/授权问题
    PERMISSION_DENIED = "PERMISSION_DENIED"
    HUMAN_AUTH_REQUIRED = "HUMAN_AUTH_REQUIRED"

    # 工具调用问题
    SCHEMA_ERROR = "SCHEMA_ERROR"
    TOOL_CALL_ERROR = "TOOL_CALL_ERROR"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"

    # 系统问题
    SYSTEM_ERROR = "SYSTEM_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"

    # 不可逆冲突
    IRREVERSIBLE_CONFLICT = "IRREVERSIBLE_CONFLICT"