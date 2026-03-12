# app/models/agent_summary.py

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import String, DateTime, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AgentSummary(Base):
    """
    Agent 执行复盘摘要
    
    分为两层：
    1. User-facing summary - 给用户看，不持久化
    2. Agent retrospective - 给系统/研发/adaptive policy 用，持久化
    """

    __tablename__ = "agent_summaries"

    # ===============================
    # 核心标识
    # ===============================
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Agent Summary UUID")
    agent_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, comment="Agent run unique identifier")
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True, comment="Associated project ID")
    cost_summary_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True, comment="Associated cost summary ID")

    # ===============================
    # 流程执行摘要
    # ===============================
    state_path: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list, comment="List of states entered during execution")
    wait_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Number of times entered S_WAIT_USER state")
    retry_count_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Total retry attempts across all states")
    human_correction_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Number of human correction loops in S4")
    validation_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Total validation rounds performed")
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Number of publish attempts in S8")

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="Agent run start timestamp")
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, comment="Agent run finish timestamp")
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Total execution duration in milliseconds")
    final_outcome: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Final outcome: success or failed")

    # ===============================
    # 数据质量与人工介入摘要
    # ===============================
    initial_validation_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(
    JSON, nullable=True,
    comment="""
    每类文件第一次 validate 的状态：
    {
        "material_cost": {
            "status": "blocked",
            "blocked_count": 5,
            "warning_count": 3,
            "top_error_codes": {"MISSING_REQUIRED_FIELD": 3, "PRICE_ANOMALY": 2}
        },
        "part_cost": {...},
        "labor_cost": {...},
        "logistics_cost": {...}
    }
    """
    )

    final_validation_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True,
        comment="""
        每类文件最终状态：
        {
            "material_cost": {"status": "ok", "blocked_count": 0, "warning_count": 0},
            ...
        }
        """
    )

    confirmed_warning_count: Mapped[Dict[str, int]] = mapped_column(
        JSON, nullable=False, default=dict,
        comment="""
        每种文件类型被人工确认通过的 warning 数量：
        {
            "material_cost": 2,
            "part_cost": 0,
            "labor_cost": 1
        }
        """
    )

    edited_item_count: Mapped[Dict[str, int]] = mapped_column(
        JSON, nullable=False, default=dict,
        comment="""
        每种文件类型被人工编辑过的 item 数量：
        {
            "material_cost": 5,
            "part_cost": 9,
            "labor_cost": 8
        }
        """
    )

    top_error_codes: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="""
        本轮最频繁的错误代码（全局 top-k），如 ["MISSING_REQUIRED_FIELD", "PRICE_ANOMALY", ...]
        注意：各 file type 的 top_error_codes 在 snapshot 内部记录
        """
    )

    manually_confirmed_categories: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list,
        comment="""
        人工确认的异常类别，如 ["price_mismatch", "missing_quantity", ...]
        """
    )

    # ===============================
    # RCA / 优化建议摘要（固定 Schema）
    # ===============================
    success_factors: Mapped[List[str]] = mapped_column(
        JSON, nullable=True, default=list,
        comment="""
        做的好的地方：
        ["自动字段识别准确", "校验规则有效", "人工反馈快速响应"]
        """
    )

    frictions: Mapped[List[str]] = mapped_column(
        JSON, nullable=True, default=list,
        comment="""
        流程摩擦点：
        ["S4 循环次数过多", "文件类型确认不清晰", "推送选项复杂"]
        """
    )

    improvement_hints: Mapped[List[str]] = mapped_column(
        JSON, nullable=True, default=list,
        comment="""
        改进建议：
        ["增加字段自动推导", "简化 S4 修正界面", "支持批量确认"]
        """
    )

