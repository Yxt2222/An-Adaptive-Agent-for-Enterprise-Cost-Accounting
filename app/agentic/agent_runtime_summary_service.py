# app/services/agent_runtime_summary_service.py

from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from collections import Counter, defaultdict
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agentic.schemas.agent_summary import AgentSummary
from app.agentic.schemas.tool_result import ToolResult
from app.agentic.fsm.FSMContect import FSMContext
from app.agentic.fsm.enums import CostCalcState
from app.agentic.fsm.global_setting import RETRYABLE_ERRORS


class AgentSummaryCollector:
    """
    Agent Summary 收集器
    
    职责：
    - 监听 runtime 关键事件
    - 维护一份与 agent_run_id 一一对应的 AgentSummary 草稿
    - 以结构化、规则化方式增量更新
    - 在终态统一 finalize
    - 持久化 agent_summaries
    
    明确不负责：
    - FSM 裁决
    - FSMContext 修改
    - 不执行工具
    - 不生成用户态自然语言长总结
    - 不替代 AuditLog
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._draft: Optional[AgentSummary] = None
        self._is_human_correction_finished = False
        
        # 用于收集错误代码
        self._error_codes_histogram: Counter = Counter()
        
        # S4 correction cycle 标记
        self._last_validated_state: Optional[CostCalcState] = None
    
    def start_run(
        self,
        *,
        agent_run_id: str,
        operator_id: str,
    ) -> None:
        """
        RuntimeStarted 事件
        
        用途：初始化 summary
        更新字段：id, agent_run_id, started_at, operator_id
        """
        self._draft = AgentSummary(
            id=str(uuid4()),
            agent_run_id=agent_run_id,
            operator_id=operator_id,
            started_at=datetime.now(),
            # 初始化默认值
            project_id=None,
            cost_summary_id=None,
            state_path=[],
            wait_count=0,
            retry_count_total=0,
            human_correction_rounds=0,
            validation_rounds=0,
            publish_attempts=0,
            duration_ms=None,
            final_outcome=None,
            initial_validation_snapshot=None,
            final_validation_snapshot=None,
            confirmed_warning_count={},
            edited_item_count={},
            top_error_codes=[],
            manually_confirmed_categories=[],
            success_factors=[],
            frictions=[],
            improvement_hints=[],
        )
    
    def on_tool_observed(
        self,
        *,
        tool_result: ToolResult,
    ) -> None:
        """
        ToolObserved 事件
        
        用途：吸收 tool 级信号
        更新字段来源：
        - project_id (S2 成功后)
        - cost_summary_id (S5 成功后)
        - validation_rounds, initial_validation_snapshot, final_validation_snapshot 草稿, top_error_codes
        - edited_item_count, edited_file_types
        - confirmed_warning_count, manually_confirmed_categories
        - publish_attempts
        """
        if not self._draft:
            return
        
        tool_name = tool_result.tool_name
        
        # S2 成功 → 更新 project_id
        if tool_name == "create_project_tool" and tool_result.ok and tool_result.data:
            self._draft.project_id = tool_result.data.get("id")
        
        # S5 成功 → 更新 cost_summary_id
        if tool_name == "generate_cost_summary_tool" and tool_result.ok and tool_result.data:
            self._draft.cost_summary_id = tool_result.data.get("id")
        
        # validate_file_tool → 更新验证相关
        if tool_name == "validate_file_tool" and tool_result.ok and tool_result.data:
            self._update_validation_signals_from_report(tool_result.data, is_initial=True)
        
        # batch_edit_items_tool → 更新编辑统计 + 更新验证相关
        if tool_name == "batch_edit_items_tool" and tool_result.ok and tool_result.data:
            edit_summary = tool_result.data.get("edit_summary", {})
            validation_report = tool_result.data.get("validation_report", {})
            self._update_edit_statistics(edit_summary)
            self._update_validation_signals_from_report(validation_report, is_initial=False)
        
        # batch_confirm_items_tool → 更新确认统计 + 更新验证相关
        if tool_name == "batch_confirm_items_tool" and tool_result.ok and tool_result.data:
            confirm_summary = tool_result.data.get("confirm_summary", {})
            validation_report = tool_result.data.get("validation_report", {})
            self._update_confirm_statistics(confirm_summary)
            self._update_validation_signals_from_report(validation_report, is_initial=False)
        
        # cost_report_publish_tool → 更新推送统计
        if tool_name == "cost_report_publish_tool":
            self._draft.publish_attempts += 1
        
        # S4 correction cycle 标记
        # 当有验证工具成功时，清除标记
        if tool_name == "validate_file_tool":
            self._is_human_correction_finished = False
    
    def on_retry(
        self,
        ctx: FSMContext,
    ) -> None:
        """
        RetryObserved 事件
        
        用途：记录系统不稳定性
        更新字段：retry_count_total
        """
        if not self._draft:
            return
        #执行重试事件条件判断
        self._draft.retry_count_total += 1
    
    def on_transition(
        self,
        *,
        ctx: FSMContext,
    ) -> None:
        """
        TransitionObserved 事件
        该工具调用发生在Apply transition之后
        
        用途：记录状态轨迹
        更新字段：
        - state_path
        - wait_count (若转入 S_WAIT_USER）
        """
        from_state = ctx.last_transition_from
        to_state = ctx.last_transition_to
        if not self._draft:
            return
        
        # 记录状态路径
        if to_state:
            self._draft.state_path.append(to_state.value)
        
        # 转入 S_WAIT_USER 时计数
        if to_state == CostCalcState.S_WAIT_USER:
            self._draft.wait_count += 1
        
        # 检测 S4 correction cycle
        # 从 S4_VALIDATE_CORRECTION_LOOP 转出，且之前有 edit+validate 行为的成功执行，记一轮
        if from_state == CostCalcState.S4_VALIDATION_CORRECTION_LOOP:
            if self._is_human_correction_finished:
                self._draft.human_correction_rounds += 1
                self._is_human_correction_finished = False
    
    def finalize(
        self,
        *,
        ctx: FSMContext,
    ) -> AgentSummary:
        """
        RuntimeFinished 事件
        
        用途：终态定稿
        更新字段：
        - finished_at, duration_ms, final_validation_snapshot
        - success_factors, frictions, improvement_hints
        - final_outcome
        """
        
        if not self._draft:
            raise ValueError("AgentSummaryCollector not started")
        
        # 更新时间信息
        self._draft.finished_at = datetime.now()
        if self._draft.started_at:
            self._draft.duration_ms = int(
                (self._draft.finished_at - self._draft.started_at).total_seconds() * 1000
            )
        
        # 更新最终验证快照（从 ctx 或草稿中获取）
        self._draft.final_validation_snapshot = self._get_final_validation_snapshot(ctx)
        
        #更新top_error_codes
        self._draft.top_error_codes = [
            code for code, _ in self._error_codes_histogram.most_common(2)
        ]
                
        # 生成 RCA / 优化建议（基于模板）
        improvement_data = self._generate_finalize_tags(ctx)
        self._draft.success_factors = improvement_data["success_factors"]
        self._draft.frictions = improvement_data["frictions"]
        self._draft.improvement_hints = improvement_data["improvement_hints"]
        
        # 设置最终结果
        if ctx.current_state.value == "S8_DONE":
            self._draft.final_outcome = "success"
        else:
            self._draft.final_outcome = "failed"

        # 保存到数据库
        self.db.add(self._draft)
        self.db.flush()
        
        return self._draft
    
    # ===============================
    # 内部辅助方法
    # ===============================
    
    def _update_validation_signals_from_report(
        self,
        validation_report: Dict[str, Any],
        is_initial: bool,
    ) -> None:
        """
        传入ToolResult.data -> validation_report.model_dump()
        从 ValidationReportDTO 更新验证信号
        """
        if not self._draft:
            return
        
        file_type = validation_report.get("file_type")
        validation_summary = validation_report.get("summary",{})
        #静态检验（虽然我觉得不可能不是str）
        if not isinstance(file_type, str):
                return
            
        # 构建 snapshot 条目
        snapshot_entry = {
            "is_ready_for_summary": validation_summary.get("is_ready_for_summary", ""),
            "total_items": validation_summary.get("total_items", 0),
            "ok_count": validation_summary.get("ok_count", 0),
            "confirmed_count": validation_summary.get("confirmed_count", 0),
            "warning_count": validation_summary.get("warning_count", 0),
            "blocked_count": validation_summary.get("blocked_count", 0),
        }
        
        # 首次验证 → 写入 initial_validation_snapshot
        if is_initial:
            #静态检验
            if self._draft.initial_validation_snapshot is None:
                self._draft.initial_validation_snapshot = {}
            
            self._draft.initial_validation_snapshot[file_type] = snapshot_entry
        
        # 收集错误代码到 histogram
        for issue_key in ("blocked_items", "warning_items"):
            for issue in validation_report.get(issue_key, []):
                self._error_codes_histogram.update(issue.get("error_codes", []))
        # 增量更新草稿 final_validation_snapshot
        if self._draft.final_validation_snapshot is None:
            self._draft.final_validation_snapshot = {}
        self._draft.final_validation_snapshot[file_type] = snapshot_entry
        
        self._draft.validation_rounds += 1
    
    def _update_edit_statistics(self, edit_data: Dict[str, Any]) -> None:
        """
        更新编辑统计
        edit_data:
        {
            "file_type":str" ("material_cost" | "part_cost" | "labor_cost" | "logistics_cost"),
            "edited_count": int, # 本次编辑的条目数量
        }
        用户apply change set的时候cordinator layer会拿到file type和edited item number。
        """
        if not self._draft:
            return
        
        edited_count = edit_data.get("edited_count", 0)
        file_type = edit_data.get("file_type")
        
        # 更新 edited_item_count,赋值比追加更鲁棒
        if file_type:
            self._draft.edited_item_count[file_type] = (
                self._draft.edited_item_count.get(file_type, 0) + edited_count
            )
            
        # 标记 S4 correction cycle
        self._is_human_correction_finished = True
    
    def _update_confirm_statistics(self, confirm_data: Dict[str, Any]) -> None:
        """
        更新确认统计
        confirm_data:
        {
            "file_type":str" ("material_cost" | "part_cost" | "labor_cost" | "logistics_cost"),
            "confirmed_count": int, # 本次确认的 warning 条目数量
            “categories”: List[str] # 本次确认的异常类别，confirmed items 的 error_codes
        }
        用户apply change set的时候cordinator layer会拿到file type和confirmed item number。
        """
        if not self._draft:
            return
        
        # 确认的 warning 数量
        confirmed_count = confirm_data.get("confirmed_count", 0)
        file_type = confirm_data.get("file_type")
        
        if file_type:
            self._draft.confirmed_warning_count[file_type] = (
                self._draft.confirmed_warning_count.get(file_type, 0) + confirmed_count
            )
        
        # 人工确认的异常类别
        categories = confirm_data.get("categories", [])
        self._draft.manually_confirmed_categories.extend(categories)
        
        # 标记 S4 correction cycle
        self._is_human_correction_finished = True
    
    def _get_final_validation_snapshot(
        self,
        ctx: FSMContext,
    ) -> Dict[str, Any]:
        """
        获取最终验证快照（草稿）
        优先从 ctx 获取最新的验证报告，覆盖草稿中的快照
        """
        
        # 如果 ctx 中的快照完整（4类文件都有），则直接返回(此处暂时写死逻辑)
        if len(ctx.validation_reports) == 4:
            final_validation_snapshot = {}
            for file_type, dto in ctx.validation_reports.items():
                validation_summary = dto.summary
                # 构建 snapshot 条目
                snapshot_entry = {
                    "is_ready_for_summary": validation_summary.is_ready_for_summary,
                    "total_items": validation_summary.total_items,
                    "ok_count": validation_summary.ok_count,
                    "confirmed_count": validation_summary.confirmed_count,
                    "warning_count": validation_summary.warning_count,
                    "blocked_count": validation_summary.blocked_count,
                }
                # 从 ctx 获取快照
                final_validation_snapshot[file_type] = snapshot_entry
            return final_validation_snapshot
        
        # 从草稿获取
        return self._draft.final_validation_snapshot if self._draft and self._draft.final_validation_snapshot else {}
    
    def _generate_finalize_tags(
        self,
        ctx: FSMContext,
    ) -> Dict[str, List[str]]:
        """
        生成终态标签（success_factors, frictions, improvement_hints）
        
        基于模板/规则化，避免 LLM 自由生成
        """
        success_factors: List[str] = []
        frictions: List[str] = []
        improvement_hints: List[str] = []
        
        # 1️⃣ 基于 final_outcome 分析
        outcome = ctx.current_state.value if ctx else "unknown"
        #任务执行成功的判别标准：成功进入S8_DONE,
        if outcome == "S8_DONE":
            success_factors.append("流程完整执行成功")
        if not self._draft:
            return {
                "success_factors": [],
                "frictions": [],
                "improvement_hints": [],
            }

        # 2️⃣ 基于 human_correction_rounds 分析
        if self._draft.human_correction_rounds <= 4:
            success_factors.append("数据质量较高，需人工修正少")
        elif self._draft.human_correction_rounds > 5:
            frictions.append("人工修正循环次数过多，需优化数据质量检查")
        
        # 3️⃣ 基于 wait_count 分析
        if self._draft.wait_count > 3:
            frictions.append("多次进入等待状态，可能需优化交互引导")
        
        # 4️⃣ 基于 retry_count_total 分析
        if self._draft.retry_count_total > 3:
            frictions.append("系统重试次数较多，可能需增强容错能力")
        
        # 5️⃣ 基于 validation_rounds 分析
        if self._draft.validation_rounds > 4:
            frictions.append("验证轮次过多，可能需优化校验规则或数据模板")
        
        # 6️⃣ 基于 top_error_codes 分析
        top_errors = self._draft.top_error_codes if self._draft else []
        if "NEGATIVE_VALUE" in [e for e, _ in top_errors]:
            improvement_hints.append("建议增加负值数据辅助修正")
        
        if "RULE_INCONSISTENT" in [e for e, _ in top_errors]:
            improvement_hints.append("建议增加价格异常检测容错区间")
        
        if "MISSING_SYSTEM" in [e for e, _ in top_errors]:
            improvement_hints.append("建议建立材料配件特征数据库，未来自动补全相应字段")
        
        # 7️⃣ 基于 edited_item_count 分析
        total_edits = sum(self._draft.edited_item_count.values())
        if total_edits > 20:
            frictions.append("人工编辑条目数量较多，可能需优化数据质量")
        
        # 8️⃣ 基于 publish_attempts 分析
        if self._draft.publish_attempts > 1:
            frictions.append("推送重试，可能需检查推送服务稳定性")
        
        # 9️⃣ 基于 manually_confirmed_categories 分析
        if "MISSING_SYSTEM" in self._draft.manually_confirmed_categories:
            improvement_hints.append("部分缺失字段是被人工允许的，建议建立材料配件特征数据库，未来自动补全相应字段")
            
        return {
            "success_factors": success_factors,
            "frictions": frictions,
            "improvement_hints": improvement_hints,
        }


class AgentRuntimeSummaryService:
    """
    Agent Runtime Summary 服务
    
    职责：
    - 协调 AgentSummaryCollector 的生命周期
    - 作为独立组件，不进入 FSMContext，也不污染 TransitionEngine
    - 监听 6 类事件并转发给 Collector
    - 提供 finalize 接口落库
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._collector: Optional[AgentSummaryCollector] = None
    
    def start_run(
        self,
        *,
        agent_run_id: str,
        operator_id: str,
    ) -> None:
        """
        启动收集器
        """
        self._collector = AgentSummaryCollector(self.db)
        self._collector.start_run(agent_run_id=agent_run_id, operator_id=operator_id)
    
    def on_tool_observed(
        self,
        *,
        tool_result: ToolResult,
    ) -> None:
        """
        工具调用事件
        """
        if self._collector:
            self._collector.on_tool_observed(
                tool_result=tool_result,
            )
    
    def on_retry(
        self,
        *,
        ctx: FSMContext,
    ) -> None:
        """
        重试事件
        """
        # Retryobserved trigger 条件判断
        if ctx.last_error_type in RETRYABLE_ERRORS and ctx.last_transition_to == ctx.last_transition_from:
            if self._collector:
                self._collector.on_retry(
                    ctx=ctx,
                )
    
    def on_transition(
        self,
        *,
        ctx: FSMContext,
    ) -> None:
        """
        状态转换事件
        """
        if self._collector:
            self._collector.on_transition(
                ctx=ctx,
            )
    
    def finalize(
        self,
        *,
        ctx: FSMContext,
    ) -> AgentSummary | None:
        """
        终态 finalize，落库
        """
        #finalize trigger 条件判断，只有进入 S8_DONE 或 S_ERR_ESCALATE 才触发 finalize 逻辑
        if ctx.current_state not in {CostCalcState.S8_DONE, CostCalcState.S_ERR_ESCALATE}:
            return None
        if not self._collector:
            raise ValueError("AgentSummaryCollector not started")
        
        summary = self._collector.finalize(ctx=ctx)
        
        # 清理 Collector 实例，准备下一次Agent Runtime
        self._collector = None
        return summary
