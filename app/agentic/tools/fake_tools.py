# app/agentic/tools/fake_tools.py
from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry


def ping(text: str) -> dict:
    print("ping tool called with:", text)
    return {"echo": text}

#正例测试函数
def create_project_success_tool(raw_name: str):
    return ToolResult(
            tool_name="create_project_success_tool",
            ok=True,
            data={"project_id": "P123"},
            explanation="Project created successfully.",
            side_effect=True,
            irreversible=True
        )
#负例测试函数
def create_project_failure_tool(raw_name: str):
    return ToolResult(
            tool_name="create_project_failure_tool",
            ok=False,
            error_type=ErrorType.SYSTEM_ERROR,
            error_message="Database temporarily unavailable.",
            side_effect=False
        )
    
    
tool_registry.register(
        ToolSpec(
            name="create_project_success_tool",
            func=create_project_success_tool,
            description="Mock create project success",
            input_schema={},
            output_schema='str',
            risk_profile=ToolRiskProfile(
                modifies_persistent_data=True,
                irreversible=True
            )
        )
    )
tool_registry.register(
        ToolSpec(
            name="create_project_failure_tool",
            func=create_project_failure_tool,
            description="Mock create project failure",
            input_schema={},
            output_schema='str',
            risk_profile=ToolRiskProfile(
                modifies_persistent_data=True,
                irreversible=True
            )
        )
    )