# app/agentic/execution/executor.py

from typing import Dict, Any
from app.agentic.tools.registry import ToolRegistry
from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType

class ToolExecutionError(Exception):
    pass

class PythonExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, *, tool_name: str, args: Dict[str, Any], allowlist: set[str]) -> ToolResult:
        '''
        Execute a tool by name with given arguments, enforcing an allowlist.
        steps:
        1) check allowlist
        2) lookup tool spec
        3) execute tool function with args 
        4) return result in a standard format, raise System error when result is not ToolResult
        param:
        tool_name: str - The name of the tool to execute.
        args: Dict[str, Any] - The arguments to pass to the tool.
        allowlist: set[str] - The set of allowed tool names.
        '''
       # 1️ allowlist gate
        if tool_name not in allowlist:
            return ToolResult(
                ok=False,
                error_type=ErrorType.TOOL_NOT_ALLOWED,
                error_message=f"{tool_name} is not allowed in current state.",
                explanation="This tool cannot be used in the current FSM state.",
                side_effect=False,
                irreversible=False
            )

        # 2 lookup
        spec = self.registry.get(tool_name)
        if not spec:
            return ToolResult(
                ok=False,
                error_type=ErrorType.SYSTEM_ERROR,
                error_message=f"Tool '{tool_name}' not found in registry.",
                explanation="This is a system configuration error. Escalate.",
                side_effect=False,
                irreversible=False
            )

        # 3️ execute
        try:
            result = spec.func(**args)
            #如果返回不是ToolResult，说明tool实现有问题，属于系统错误
            if not isinstance(result, ToolResult):
                return ToolResult(
                    ok=False,
                    error_type=ErrorType.SYSTEM_ERROR,
                    error_message="Tool did not return ToolResult instance.",
                    explanation="Tool implementation error. Escalate.",
                    side_effect=False,
                    irreversible=False
                )

            return result

        except Exception as e:
            # 理论上不应该进入这里（tool 内部已分类）
            return ToolResult(
                ok=False,
                error_type=ErrorType.SYSTEM_ERROR,
                error_message=str(e),
                explanation="Unhandled exception in executor. Escalate.",
                side_effect=False,
                irreversible=False
            )