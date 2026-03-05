from app.agentic.schemas.dto.explan_validate_report_dto import ExplainValidationReportInput
from app.agentic.schemas.dto.validate_report_dto import ValidationReportDTO

    
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry

# Part 1 辅助工具
def build_validation_explanation(report: ValidationReportDTO) -> str:

    summary = report.summary
    lines = []
    lines.append(f"文件类型: {report.file_type}")
    lines.append(
        f"总条目 {summary.total_items} 条，其中 "
        f"{summary.ok_count} 条正常，"
        f"{summary.warning_count} 条警告，"
        f"{summary.blocked_count} 条阻断。"
    )
    if report.blocked_items:
        lines.append("\n阻断错误（必须修复）：")

        for item in report.blocked_items[:10]:
            lines.append(
                f"- Item {item.item_id}: {item.explanation}"
            )
    if report.warning_items:
        lines.append("\n警告项（建议检查）：")

        for item in report.warning_items[:10]:
            lines.append(
                f"- Item {item.item_id}: {item.explanation}"
            )
    if summary.is_ready_for_summary:
        lines.append("\n所有数据已通过校验，可以生成成本汇总。")
    else:
        lines.append("\n请修复上述问题后重新验证。")
        
    return "\n".join(lines)

# Part 2 Tool 实现
def explain_validation_report_tool(args: dict) -> ToolResult:

    try:
        input_dto = ExplainValidationReportInput(**args)
        report = ValidationReportDTO(**input_dto.validation_report)
        explanation = build_validation_explanation(report)
        return ToolResult(
            ok=True,
            tool_name="explain_validation_report_tool",
            data={
                "explanation": explanation
            },
            explanation="Validation report explained successfully. Please send the explanation to employees to help them understand the validation results.",
        )

    except Exception as e:

        return ToolResult(
            ok=False,
            tool_name="explain_validation_report_tool",
            error_type=ErrorType.SYSTEM_ERROR,
            error_message=str(e),
        )
# Part 3 ToolSpec 注册      
tool_registry.register(
        ToolSpec(
            name="explain_validation_report_tool",
            func=explain_validation_report_tool,
            description="Explain validation report",
            input_schema={"arg":"ValidationReportDTO.model_dump()"},
            output_schema='str',
            risk_profile=ToolRiskProfile(
                modifies_persistent_data=False,
                irreversible=True,
                deletes_data=False,
                affects_multiple_records=False,
                require_human_auth=False
            )
        )
    )