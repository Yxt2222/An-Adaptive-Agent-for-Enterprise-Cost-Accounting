# app/agentic/tools/cost_report_publish_tool.py

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import sqlite3

from app.agentic.schemas.tool_result import ToolResult
from app.agentic.schemas.error_type import ErrorType

from app.models.cost_summary import CostSummary
from app.models.project import Project
from app.services.audit_log_service import AuditLogService
from app.services.publish_report_service import PublishReportService

from app.agentic.schemas.tool_spec import ToolSpec
from app.agentic.schemas.risk_profile import ToolRiskProfile
from app.agentic.tools.registry import tool_registry


# ===============================
# 错误分类函数
# ===============================

def _classify_publish_error(e: Exception) -> tuple[ErrorType, str, str]:
    msg = str(e).lower()
    
    # DB/系统类
    if isinstance(e, (OperationalError, sqlite3.OperationalError, SQLAlchemyError)):
        return ErrorType.DATABASE_ERROR, msg, "Database error occurred. Retry may work. If repeated, escalate to ERR_ESCALATE with audit details."
    # config设置类
    if isinstance(e, FileNotFoundError):
        return ErrorType.FILE_NOT_FOUND, msg, "channal config file not found.fallback path is not defined"
    # 推送相关
    if "webhook" in msg or "发送" in msg or "smtp" in msg:
        return ErrorType.EXTERNAL_SERVICE_ERROR, msg, "Publish service error (e.g., webhook failure, email sending failure). Check the error message for details and try again."
    
    if "channels config file is empty" in msg:
        return ErrorType.FILE_NOT_FOUND, msg, "Channels config file is empty"

    return ErrorType.SYSTEM_ERROR, msg, "Unknown system error. Retry and escalate"
# ===============================
# 工具实现
# ===============================

def cost_report_publish_tool(
    *,
    db: Session,
    cost_summary_id: str,
    user_publish_query: Optional[str] = None,
    operator_id: str,
) -> ToolResult:
    """
    调用服务report_publish_service解析意图（实行三步fallback， 意图解析-关键词匹配-默认网页推送），
    发送报告到企业微信/钉钉/邮件/网页端。
    
    Side effects:
    - 解析用户发布意图（LLM + fallback）
    - 发送报告到指定渠道（企业微信/钉钉/邮件/网页端）
    
    Preconditions:
    - CostSummary 必须存在且为 ACTIVE
    - report_storage_path 必须存在
    
    Returns:
        推送结果
    """
    audit = AuditLogService(db)
    publish_service = PublishReportService()
    
    try:
        # 1️⃣ 加载 CostSummary
        cost_summary = db.query(CostSummary).get(cost_summary_id)
        if not cost_summary:
            return ToolResult(
                tool_name="cost_report_publish_tool",
                ok=False,
                error_type=ErrorType.FILE_NOT_FOUND,
                error_message=f"CostSummary not found: {cost_summary_id}",
                explanation="指定的成本汇总不存在",
                side_effect=False,
                irreversible=False,
            )
        
        # 2️⃣ 检查报告文件
        if not cost_summary.report_storage_path:
            return ToolResult(
                tool_name="cost_report_publish_tool",
                ok=False,
                error_type=ErrorType.FILE_NOT_FOUND,
                error_message="No report file generated",
                explanation="请先生成成本报告后再发布",
                side_effect=False,
                irreversible=False,
            )
        
        # 3️⃣ 加载项目信息
        project = db.query(Project).get(cost_summary.project_id)
        project_name = project.normalized_name if project else "未知项目"
        
        # 4️⃣ 准备报告数据
        report_data = {
            "project_name": project_name,
            "total_cost": f"{cost_summary.total_cost:.2f}",
            "report_file_name": cost_summary.report_file_name,
            "report_storage_path": cost_summary.report_storage_path,
            "generated_at": cost_summary.report_generated_at.strftime("%Y-%m-%d %H:%M:%S") if cost_summary.report_generated_at else "",
            "download_url": f"/api/cost-reports/{cost_summary_id}/download",
        }
        
        # 5️⃣ 解析发布意图
        user_query = user_publish_query or ""
        intent = publish_service.parse_publish_intent(user_query)
        # 检查intent是否正常：
        if not intent:
            return ToolResult(
                tool_name="cost_report_publish_tool",
                ok=False,
                error_type=ErrorType.SYSTEM_ERROR,
                error_message="Failed to parse publish intent",
                explanation="无法解析发布意图，可能是user input不够清晰，LLM连接失败类错误，LLM解析错误，尝试retry。",
                side_effect=False,
                irreversible=False,
            )
        # 6️⃣ 发送到指定渠道
        send_result = publish_service.send_report_to_channel(
            channel=intent["channel"],
            targets=intent["targets"],
            report_data=report_data,
        )
        # 检查发送结果并返回ToolResult
        if not send_result["success"]:
            return ToolResult(
                tool_name="cost_report_publish_tool",
                ok=False,
                error_type=ErrorType.TOOL_CALL_ERROR,
                error_message=send_result.get("error", "Unknown send error"),
                explanation=f"报告发送失败: {send_result.get('message', '')}",
                side_effect=False,
                irreversible=False,
            )
            
        return ToolResult(
            tool_name="cost_report_publish_tool",
            ok=True,
            data={
                "channel": send_result["channel"],
                "sent_to": send_result["sent_to"],
                "message": send_result["message"],
                "fallback_used": intent.get("fallback_used", False),
                "llm_parsed": intent.get("llm_parsed", False),
            },
            explanation=(
                f"报告已成功发布到 {send_result['channel']}。"
                f"{send_result['message']} "
                f"{'(使用fallback解析)' if intent.get('fallback_used') else '(LLM解析)'}"
            ),
            side_effect=True,
            irreversible=False,
            audit_ref_id=cost_summary.id,
        )
        
    except Exception as e:
        db.rollback()
        error_type, error_message, explanation = _classify_publish_error(e)
        return ToolResult(
            tool_name="cost_report_publish_tool",
            ok=False,
            error_type=error_type,
            error_message=error_message,
            explanation=explanation,
            side_effect=False,
            irreversible=False,
        )


# ===============================
# ToolSpec 注册
# ===============================

tool_registry.register(
    ToolSpec(
        name="cost_report_publish_tool",
        func=cost_report_publish_tool,
        description=(
            "发布成本报告到指定渠道（企业微信/钉钉/邮件/网页端）。"
            "支持自然语言输入，如'发到企业微信群'、'钉钉发送'、'不发送'等。"
            "使用多层级 fallback：LLM 解析 → 关键词匹配 → 默认网页端。"
        ),
        input_schema={
            "cost_summary_id": "str",
            "user_publish_query": "str | None",
            "operator_id": "str",
        },
        output_schema={
            "tool_name": "str",
            "ok": "bool",
            "error_type": "Optional[ErrorType]",
            "error_message": "Optional[str]",
            "data": {
                "channel": "str",
                "sent_to": "List[str]",
                "message": "str",
                "fallback_used": "bool",
                "llm_parsed": "bool",
            },
            "explanation": "Optional[str]",
            "side_effect": "bool",
            "irreversible": "bool",
            "audit_ref_id": "Optional[str]",
        },
        risk_profile=ToolRiskProfile(
            modifies_persistent_data=False,  # 只发送，不修改业务数据
            irreversible=False,
            deletes_data=False,
            affects_multiple_records=False,
            require_human_auth=False,
        ),
        example_usage='cost_report_publish_tool(cost_summary_id="xxx", user_publish_query="发到企业微信群", operator_id="u_123")',
    )
)
