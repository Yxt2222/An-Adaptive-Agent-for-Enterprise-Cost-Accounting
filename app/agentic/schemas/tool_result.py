# app/agentic/execution/tool_registry.py
from typing import Any, Dict, Optional
from pydantic import BaseModel
from app.agentic.schemas.error_type import ErrorType

class ToolResult(BaseModel):
    '''
    工具执行结果的结构化表达
    
    参数	说明
    ok: bool  - 这次调用是否完成预期操作？
    error_type: Optional[ErrorType] - 错误类型的结构化记录
    error_message: Optional[str] - 面向LLM/人类的可读解释，报错信息
    data: Optional[Dict[str, Any]] - 工具调用的结构化数据结果
    explanation: Optional[str] - 面向LLM的自然语言解释，解释调用结果，下一步建议等
    side_effect: bool - 这次调用是否有副作用是否会改变现实世界状态
    irreversible: bool - 这次调用是否不可逆/不可撤销（如删除数据）
    audit_ref_id: Optional[str] - 用于审计追踪的唯一标识符
    '''
    ok: bool  # 是否成功完成

    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None

    data: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None
    # explanation 是给 LLM 的自然语言解释 + 下一步建议

    side_effect: bool = False
    irreversible: bool = False

    audit_ref_id: Optional[str] = None