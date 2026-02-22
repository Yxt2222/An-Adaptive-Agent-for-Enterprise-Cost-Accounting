from typing import Callable, Any, Dict, Optional
from pydantic import BaseModel
from app.agentic.schemas.risk_profile import ToolRiskProfile

class ToolSpec(BaseModel):
    '''
    定义一个工具的规范，包括它的名称、功能、输入输出格式、风险评估等。
    
    参数	说明
    name	工具的唯一名称，用于注册和调用
    func	工具的实际函数实现，接受输入参数并返回输出结果
    description	工具的功能描述，包含它的作用、前置条件、副作用和风险等信息
    input_schema	定义工具输入参数的结构化 schema，便于验证和自动生成文档
    output_schema	定义工具输出结果的结构化 schema，便于验证和自动生成文档
    risk_profile	工具的风险评估，使用 ToolRiskProfile 定义工具的风险特征
    example_usage	工具的示例用法，展示如何调用这个工具以及预期的输入输出
    '''
    name: str
    func: Callable[..., Any]
    description: str#play book of a tool，做什么，前置条件，副作用，风险
    input_schema:Dict[str,Any]#定义输入参数的 schema
    output_schema:str#定义输出参数的 schema
    risk_profile:ToolRiskProfile#风险名单
    example_usage:Optional[str] = None