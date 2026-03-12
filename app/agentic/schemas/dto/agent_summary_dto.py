# app/agentic/schemas/dto/agent_summary_dto.py
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class AgentSummaryUserFacingDTO(BaseModel):
    """
    用户看到的短业务文案，不持久化
    """
    project_name: str
    total_cost: str
    cost_breakdown: Dict[str, str]  # {"material": "xxx", "part": "xxx", "labor": "xxx", "logistics": "xxx"}
    report_file_name: str
    generated_at: str
    status: str  # "成功" / "失败"
    duration: Optional[str] = None


class AgentSummaryRetrospectiveDTO(BaseModel):
    """
    Agent 回顾数据，给研发/adaptive policy 用
    """
    agent_run_id: str
    project_id: Optional[str]
    final_state: str
    
    # 流程执行摘要
    execution_summary: Dict[str, Any]
    """
    {
        "entered_states": [...],
        "wait_count": x,
        "retry_count_total": x,
        "human_correction_rounds": x,
        "validation_rounds": x,
        "duration_ms": x
    }
    """
    
    # 数据质量摘要
    data_quality_summary: Dict[str, Any]
    """
    {
        "initial_validation_snapshot": {...},
        "final_validation_snapshot": {...},
        "confirmed_warning_count": x,
        "edited_item_count": x,
        "edited_file_types": [...],
        "top_error_codes": [...],
        "manually_confirmed_categories": [...]
    }
    """
    
    # RCA / 优化建议
    improvement_summary: Dict[str, List[str]]
    """
    {
        "success_factors": [...],
        "frictions": [...],
        "improvement_hints": [...]
    }
    """


class AgentSummaryFullDTO(BaseModel):
    """
    完整 DTO，用于返回给前端
    """
    user_facing: AgentSummaryUserFacingDTO
    retrospective: Optional[AgentSummaryRetrospectiveDTO] = None


class PublishPreferenceDTO(BaseModel):
    """
    推送偏好设置
    """
    channels: List[str]  # ["web", "wechat", "dingtalk", "email"]
    notify_immediately: bool = True
