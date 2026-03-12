# app/agentic/runtime_coordinator.py

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.agentic.fsm.state_transition_engine import TransitionEngine, FSMContext
from app.agentic.agent_runtime_summary_service import (
    AgentSummaryCollector,
    AgentRuntimeSummaryService,
)
from app.agentic.execution.executor import PythonExecutor
from app.agentic.schemas.tool_result import ToolResult

from app.agentic.fsm.enums import CostCalcState
from app.services.audit_log_service import AuditLogService


class RuntimeCoordinator:
    """
    Runtime Coordinator
    
    职责：
    - 统一调度 FSM Engine、工具执行、AgentSummary 更新和事件触发
    - 核心是调度和执行，保证一轮 agent run 内各模块按顺序执行
    - 不涉及智能规划或决策逻辑（LLM observe-plan-act）
    """
    
    def __init__(
        self,
        db: Session,
        executor: PythonExecutor,
        agent_run_id:str
    ):
        self.fsm_engine = TransitionEngine(agent_run_id=agent_run_id)
        #todo: executor 尚未正式实现，未来可改
        self.executor = executor
        self.summary_service = AgentRuntimeSummaryService(db = db)
        #todo: runtime_audit_service 尚未正式实现，未来可改
        self.audit_service = AuditLogService(db = db)
    
    # ===============================
    # 核心方法：生命周期管理
    # ===============================
    
    def initialize(
        self,
        *,
        agent_run_id: str,
        operator_id: str = "Agentic system",
    ) -> FSMContext:
        """
        初始化 Coordinator
        
        用途：
        1. 创建 FSMContext
        2. 初始化 FSM Engine
        3. 触发 RuntimeStarted 事件
        4. 记录 AgentRunCreated 审计日志
        
        Returns:
            初始化后的 FSMContext
        """
        # 1️⃣ 记录 AgentRunCreated 审计日志
        self.audit_service.record_create(
            project_id=None,  # 初始化时 project_id 尚未知
            entity_type="AgentRun",
            entity_id=agent_run_id,
            operator_id=operator_id,
        )
        # 2️⃣ 触发 RuntimeStarted 事件
        self.summary_service.start_run(
            agent_run_id=agent_run_id,
            operator_id=operator_id,
        )
        return self.fsm_engine.ctx
    
    def run_one_step(
        self,
        ctx: FSMContext,
        tool_name: str, 
        args: Dict[str, Any]
    ) -> FSMContext:
        """
        执行一步 FSM 步骤
        
        步骤顺序：
        1. 调用 Executor 执行对应工具
        2. 捕获 ToolResult
        3. 调用 FSMEngine.run_one_step() → (ctx, decision)
        4. 调用 handle_transition(ctx, decision)
        """
        # 初始化审查
        if not self.fsm_engine or not self.summary_service._collector:
            raise Exception("Runtime Coordinator not initialized. Call initialize() first.")
        
        
        # 1️⃣ 调用 Executor 执行对应工具（如需）
        tool_result = self._execute_tool(tool_name, args)
        
        #2️⃣ 调用 handle_tool_result(tool_result)
        if tool_result:
            self.handle_tool_result(tool_result)

        # 3️⃣ 调用 FSMEngine 裁决（更新 context + state transition）
        updated_ctx, _ = self.fsm_engine.run_one_step(tool_result=tool_result)
    
        
        # 4️⃣ 调用 handle_transition(ctx, decision)
        self.handle_transition(updated_ctx)
        
        return updated_ctx
    
    def _execute_tool(
        self,
        tool_name: str, 
        args: Dict[str, Any],
    ) -> ToolResult | None:
        """
        执行工具（封装器）
        """
        # 注意：当前 executor 是临时 mock，待正式实现
        # 正式实现后这里会调用 z正式的self.executor.execute(...)
        if not self.fsm_engine:
            return
        
        tool_result = self.executor.execute(
                tool_name=tool_name,
                args=args,
                allowlist=self.fsm_engine.get_allowed_tools(),
            )
            
        return tool_result
    
    def handle_tool_result(
        self,
        tool_result: ToolResult,
    ) -> None:
        """
        处理工具执行结果
        """
        # 触发 ToolObserved 事件
        if hasattr(self, 'summary_service'):
            self.summary_service.on_tool_observed(
                tool_result=tool_result,
            )
        #todo 审计transition决策结果
        # 记录审计日志
        if hasattr(self, 'audit_service'):
            self.audit_service.record_update(
                project_id="project haven't created" if self.fsm_engine.ctx.current_state in [CostCalcState.S0_INIT, CostCalcState.S1_INPUT_GATE] else self.fsm_engine.ctx.project_id,
                entity_type="Tool",
                entity_id=tool_result.tool_name,
                changed_attribute="executed",
                before_value=None,
                after_value="ok" if tool_result.ok else "failed",
                operator_id="Agentic system",
            )
    
    def handle_transition(
        self,
        ctx: FSMContext,
    ) -> None:
        """
        处理状态转移
        """
        # 触发 TransitionObserved 事件
        if hasattr(self, 'summary_service') and hasattr(ctx, 'last_transition_from'):
            self.summary_service.on_transition(
                ctx=ctx,
            )
        #todo 审计transition决策结果
        # 记录审计日志
        if hasattr(self, 'audit_service'):
            self.audit_service.record_update(
                project_id="project haven't created" if ctx.current_state in [CostCalcState.S0_INIT, CostCalcState.S1_INPUT_GATE] else ctx.project_id,
                entity_type="State_Transition",
                entity_id= ctx.agent_run_id,
                changed_attribute="current_state",
                before_value=ctx.last_transition_from.value if ctx.last_transition_from else None,
                after_value= ctx.last_transition_to.value if ctx.last_transition_to else None,
                operator_id="Agentic system",
            )
    
    def finalize(
        self,
        ctx: FSMContext,
    ) -> None:
        """
        结束运行，触发 RuntimeFinished 事件
        """
        # 触发 RuntimeFinished 事件
        if hasattr(self, 'summary_service'):
            self.summary_service.finalize(
                ctx=ctx,
            )
 