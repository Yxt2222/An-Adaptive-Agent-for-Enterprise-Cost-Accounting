#app/agentic/fsm/state_transition_engine.py

from app.agentic.fsm.enums import CostCalcState
from app.agentic.fsm.FSMContect import FSMContext
from app.agentic.fsm.global_setting import RETRYABLE_ERRORS, FATAL_ERRORS, REQUIRED_FILE_TYPES, VALID_VALIDATION_RESULTS, RETURN_VALIDATION_REPORT_TOOLS
from app.agentic.fsm.Transition import TransitionDecision

from typing import Callable, Optional, Dict, Any
from app.agentic.schemas.dto.validate_report_dto import ValidationReportDTO
from app.agentic.schemas.error_type import ErrorType
from app.agentic.schemas.tool_result import ToolResult

from app.agentic.tools.registry import tool_registry#注册所有工具以测试用，完工后删
from app.agentic.tools.auto_discover import discover_tools
from app.routes import report#注册所有工具以测试用，完工后删
discover_tools()

#决策引擎
class TransitionEngine:
    '''
    CostCalFSM是一个单步裁决型orchestrator Engine，其职责是在当前上下文中，决定下一个状态是什么。
    CostCalcFSM 负责根据上一步的 FSMContext 和这一步的 ToolResult 裁决下一步 state 怎么转移，
    维护 Context，并且负责管理和展示 State 相关派生属性。
    '''
    def __init__(self, context: FSMContext):
        self.ctx = context
        #-----------------------------State Dispatch -----------------------------
        self.state_dispatchers: Dict[CostCalcState, Callable] = {
            CostCalcState.S0_INIT: self._handle_s0,
            CostCalcState.S1_INPUT_GATE: self._handle_s1,
            CostCalcState.S2_CREATE_PROJECT: self._handle_s2,
            CostCalcState.S3_PARSE_FILES: self._handle_s3,
            CostCalcState.S4_VALIDATION_CORRECTION_LOOP: self._handle_s4,
            CostCalcState.S5_GENERATE_COST_SUMMARY: self._handle_s5,
            CostCalcState.S_WAIT_USER: lambda: TransitionDecision(next_state=CostCalcState.S_WAIT_USER, pause=True),
            
        }
        #----------------------------Context Update Dispatch----------------------
        self.ctxupdate_dispatchers: Dict[CostCalcState, Callable[[ToolResult], None]] = {
            CostCalcState.S0_INIT: lambda result: None,#S0状态不处理tool result
            CostCalcState.S1_INPUT_GATE: self._updatectx_s1,#S1状态不处理tool result
            CostCalcState.S2_CREATE_PROJECT: self._ctxupdate_s2,
            CostCalcState.S3_PARSE_FILES: self._ctx_update_s3,
            CostCalcState.S4_VALIDATION_CORRECTION_LOOP: self._ctx_update_s4,
            CostCalcState.S5_GENERATE_COST_SUMMARY: self._generate_cost_summary_s5
        }
        # Public API
            
    # ===============================
    # Step Execution  
    # ===============================
    def run_one_step(self, tool_result: Optional[ToolResult]) -> FSMContext:
        # 1. 更新 context
        if tool_result:
            self._update_context(tool_result)
        # 2. 执行状态裁决
        decision = self._execute_state(self.ctx.current_state)

        # 3. 错误统一处理（覆盖 decision）
        if self.ctx.last_error_type:
            decision = self._handle_error(self.ctx.last_error_type)
        # 4. 应用状态跃迁
        self._apply_transition(decision)
        
        #5. 消费瞬态信号
        self._clear_transient_signals()
        return self.ctx


    # ===============================
    # Transition Application Layer
    # ===============================

    def _apply_transition(self, decision: TransitionDecision):

        # 1 暂停优先
        if decision.pause:
            self._transition_to(CostCalcState.S_WAIT_USER)
            self.ctx.pause_reason = self.ctx.pause_reason or "WAIT_USER"
            return

        # 32 正常跳转
        self._transition_to(decision.next_state)

    def _transition_to(self, next_state: CostCalcState):
        """
        统一状态切换入口：
        - 重置 retry
        - 更新 state
        """
        if next_state != self.ctx.current_state:
            self.ctx.retry_count = 0
        
        #更新转移轨迹
        self.ctx.last_transition_from = self.ctx.current_state
        self.ctx.last_transition_to = next_state
        
        #state transition
        self.ctx.current_state = next_state

    # ===============================
    # Error Handling Layer
    # ===============================
    
    def _handle_error(self, error_type: ErrorType):
        '''
        Error_Routing: 根据错误类型进行不同的处理，例如重试、进入错误升级状态等。
        '''
        #局部状态下有限容错
        if error_type in RETRYABLE_ERRORS:
            self.ctx.retry_count += 1
            if self.ctx.retry_count <= self.ctx.max_retry:
                # stay in current state
                return TransitionDecision(next_state=self.ctx.current_state)
            else:
                return TransitionDecision(next_state=CostCalcState.S_ERR_ESCALATE)
            
        if error_type in FATAL_ERRORS:
            return TransitionDecision(next_state=CostCalcState.S_ERR_ESCALATE)

        # 其他错误默认 escalate
        return TransitionDecision(next_state=CostCalcState.S_ERR_ESCALATE)
    
    # ===============================
    # Step 1: Update Context
    # ===============================
    def _update_context(self, tool_result: ToolResult) -> None:
        """
        通用字段 + 状态定制字段写入 Context
        """
        # --- 通用字段（必须无条件写） ---
        # tool_name 如果 ToolResult 没有，可先用 audit_ref_id 或在 executor 注入
        self.ctx.last_tool = getattr(tool_result, "tool_name", None) or self.ctx.last_tool
        self.ctx.last_tool_ok = tool_result.ok
        self.ctx.last_error_type = tool_result.error_type

        # --- 状态定制字段 ---
        state = self.ctx.current_state  # 当前 state 即“请求 tool 的 state”
        handler = self.ctxupdate_dispatchers.get(state)
        if handler:
            handler(tool_result)

    def _clear_transient_signals(self) -> None:
        """
        last_error_type / last_tool_ok 属于“本步裁决信号”，消费后清空。
        last_tool 可以保留作为审计轨迹（不影响裁决）。
        """
        self.ctx.last_error_type = None
        self.ctx.last_tool_ok = None    

    # ===============================
    # Step 2: State Dispatch layer
    # ===============================
    
    def _execute_state(self, state: CostCalcState) -> TransitionDecision:
        #默认如果没有找到对应状态的handler，则认为该状态是一个终态，直接返回S9_DONE
        handler = self.state_dispatchers.get(
            state, 
            lambda: TransitionDecision(next_state=CostCalcState.S8_DONE))
        return handler()
    

    # ===============================
    # State Handlers
    # ===============================
    
    #--------------------- S0_init handler ----------------------------------------------
    def _handle_s0(self) -> TransitionDecision:
        return TransitionDecision(
            next_state=CostCalcState.S1_INPUT_GATE
        )
    #--------------------- S1_input_gate handler ----------------------------------------------
    #缺乏把raw_name从对话中提取出来更新到ctx中的方法
    def _updatectx_s1(self, tool_result: ToolResult) -> None:
        '''
        S1ctx专用字段更新函数
        extract_project_info_tool: 从对话输入中提取raw_name，更新到ctx.collected_inputs["raw_name"]中
        confirme_raw_upload_tool:确认rawfile的类型，返回id,filetype信息，更新到ctx.collected_inputs["confirmed_files"]中，
        id更新到ctx.confirmed_rawfile_id_map中
        '''
        if not tool_result.ok:
            return
        data = tool_result.data or {}

        #extract_project_info_tool
        if tool_result.tool_name == "extract_project_info_tool":
             
            raw_name = data.get("raw_name")
            if raw_name is not None:
                cleaned = raw_name.strip()
                self.ctx.project_info["raw_name"] = cleaned if cleaned else self.ctx.project_info.get("raw_name")
                      
            contract_code = data.get("contract_code")
            if contract_code is not None:
                cleaned = contract_code.strip()
                self.ctx.project_info["contract_code"] = cleaned if cleaned else self.ctx.project_info.get("contract_code")
                    
            business_code = data.get("business_code")
            if business_code is not None:
                cleaned = business_code.strip()
                self.ctx.project_info["business_code"] = cleaned if cleaned else self.ctx.project_info.get("business_code")
                    
            spec_tags = eval(data.get("spec_tags", "[]"))
            if spec_tags is not None and isinstance(spec_tags, list):
                cleaned_tags = [tag.strip() for tag in spec_tags if isinstance(tag, str) and tag.strip()]
                self.ctx.project_info["spec_tags"] = cleaned_tags if cleaned_tags else self.ctx.project_info.get("spec_tags")
                    
        #confirm_raw_upload_tool  
        elif tool_result.tool_name == "confirm_raw_upload_tool":
            raw_upload_id = data.get("raw_upload_id")
            file_type = data.get("confirmed_file_type")
            if raw_upload_id and file_type in REQUIRED_FILE_TYPES:
                self.ctx.confirmed_rawfile_id_map[file_type] = raw_upload_id
    
    def _info_ready_gate(self) -> bool:
        #从self.ctx出发，检查项目名称等基本信息是否准备好，项目名称非空即可
        raw_name = self.ctx.project_info.get("raw_name")
        return bool(raw_name and raw_name.strip())

    def _file_ready_gate(self) -> set[str]:
        #从self.ctx出发，检查文件是否准备好，返回已经确认的文件类型集合
        return set([k for k,v in self.ctx.confirmed_rawfile_id_map.items() if v is not None])
    #生成required_inputs，列表
    def _compute_required_inputs(
        self,
        info_ready: bool,
        confirmed_types: set[str]
    ) -> list[str]:

        missing = []
        if not info_ready:
            missing.append("project raw_name")

        missing_files = REQUIRED_FILE_TYPES - confirmed_types
        for ft in missing_files:
            missing.append(f"file:{ft}")
        return missing
    
    #输入门控状态的handler，检查输入是否满足要求，如果满足要求则进入下一个状态，否则进入等待用户输入状态
    def _handle_s1(self) -> TransitionDecision:

        info_ready = self._info_ready_gate()
        confirmed_types = self._file_ready_gate()
        files_ready = REQUIRED_FILE_TYPES.issubset(confirmed_types)
        required = self._compute_required_inputs(info_ready, confirmed_types)
        #pudate context required_inputs
        self.ctx.required_inputs = required

        if info_ready and files_ready:
            return TransitionDecision(
                next_state=CostCalcState.S2_CREATE_PROJECT
            )

        return TransitionDecision(
            next_state=CostCalcState.S_WAIT_USER,
            pause=True
        )
    #----------------------S2_CREATE_PROJECT handler ----------------------------------------------
    def _handle_s2(self) -> TransitionDecision:
        """
        S2状态转移规范，独立于错误处理之外。
        规范：S2 的推进必须由 context 驱动。
        - project_id 如果不存在 → 请求调用 create_project
        - file_record_id其中之一如果不存在 → 请求调用 upload_create_file_record
        - 如果所有要素齐全，进入S3_PARSE_FILES
        """
        if not self.ctx.project_id:
            return TransitionDecision(
                next_state=self.ctx.current_state,
                action={
                    "type": "call_tool",
                    "tool_name": "create_project_tool",
                    "args":{
                        "raw_name": self.ctx.project_info.get("raw_name")
                    }
                }
            )
        if not all(self.ctx.file_record_id_map.get(ft) for ft in REQUIRED_FILE_TYPES):
            return TransitionDecision(
                next_state=self.ctx.current_state,
                action={
                    "type": "call_tool",
                    "tool_name": "bind_validated_file_to_project_tool",
                    "args":{
                        "project_id": self.ctx.project_id,
                        #选择一个还没有上传绑定项目的文件类型来请求工具调用，优先级可以根据业务需求调整
                        "raw_upload_id":  [v for k,v in self.ctx.confirmed_rawfile_id_map.items() if self.ctx.file_record_id_map.get(k) is None and v is not None][0],
                    }
                }
            )
        return TransitionDecision(next_state=CostCalcState.S3_PARSE_FILES)
    
    def _ctxupdate_s2(self, result: ToolResult) -> None:
        """
        S2ctx专用字段更新函数
        s2状态可调用的两个函数，create_project_tool和upload_create_file_record_tool， 
        create_project成功：把project_id写进context
        bind_validated_file_to_project成功：把file_record_id写进context（新建对象 id 来自 ToolResult DTO）
        """
        
        if result.tool_name == "create_project_tool":
            #成功：把id写进context
            if result.ok:
                project_id = result.data.get("id") if result.data else None
                if project_id:
                    self.ctx.project_id = project_id

        if result.tool_name == "bind_validated_file_to_project_tool":
            #成功：把 file_record_id 写入 context（新建对象 id 来自 ToolResult DTO）
            if result.ok:
                data = result.data or {}
                file_type = data.get("file_type")
                file_record_id = data.get("id")
                if file_type and file_record_id and file_type in REQUIRED_FILE_TYPES:
                    self.ctx.file_record_id_map[file_type] = file_record_id
                    
# -----------------------------S3_PARSE_FILES handler ---------------------------------------------- 
    def _ctx_update_s3(self, result: ToolResult) -> None:
        '''
        S3ctx专用字段更新函数
        '''
        if result.tool_name == "parse_file_tool":
            #成功：把 parse_status 写入 context
            if result.ok and result.data:
                file_type = result.data.get("file_type")
                parse_status = result.data.get("parse_status")
                if file_type and parse_status and file_type in REQUIRED_FILE_TYPES:
                    self.ctx.parse_status_map[file_type] = parse_status
        
    def _handle_s3(self) -> TransitionDecision:
        """
        S3_PARSE_FILES 专属字段相关裁决逻辑,不必负责error handling和retry。
        •	如果还有文件没有完成 parse → stay in S3_PARSE_FILES，等待下一轮 parse_file_tool 的调用
        •	所有 parsed → S4_VALIDATE_FILES
        •	存在 failed → S_WAIT_USER（要求重传）
        """
        expected_files = set(self.ctx.file_record_id_map.keys())
        parsed_files = set(self.ctx.parse_status_map.keys())
        
        # 如果还没全部尝试 parse，不跳转（等待继续调用 parse）
        if parsed_files < expected_files:
            return TransitionDecision(
                                      next_state=self.ctx.current_state,
                                      pause=False
                                      )
        # 全部 parsed
        if all(status == "parsed" for status in self.ctx.parse_status_map.values()):
            return TransitionDecision(
                next_state=CostCalcState.S4_VALIDATION_CORRECTION_LOOP
            )
        else:  # 存在 failed
            return TransitionDecision(
                next_state=CostCalcState.S_WAIT_USER,
                pause=True,
            )
        #跨轮次污染问题？

# -----------------------------S4_VALIDATE_CORRECTION_LOOP handler ---------------------------------------------- 
    def _ctx_update_s4(self, result: ToolResult) -> None:
        '''
        S4ctx专用字段更新函数
        
        '''
        #validate_file_tool或batch_edit_items_tool或batch_confirm_items_tool，会返回ValidationReportDTO，需要写入ctx.
        if result.tool_name in RETURN_VALIDATION_REPORT_TOOLS:
            #成功：把 validation_status 写入 context
            if result.ok and result.data:  # if data=None → 不更新 ctx,因为validate_file_tool或batch_edit_items_tool没触发Validation
                report = ValidationReportDTO(**result.data)
                file_type = report.file_type
                validation_status = report.validation_status
                if file_type in REQUIRED_FILE_TYPES:
                    if validation_status in VALID_VALIDATION_RESULTS:
                        self.ctx.validation_status_map[file_type] = validation_status
                    self.ctx.validation_reports[file_type] = report
        
                    
    def _handle_s4(self) -> TransitionDecision:
        """
        S4_VALIDATE_CORRECTION_LOOP 专属裁决逻辑
        •	如果还有文件没有完成 validate → stay in S4_VALIDATE_CORRECTION_LOOP，等待下一轮 validate_file_tool 的调用
        •	∀ validation_status in {ok, confirmed} → S5_GENERATE_COST_SUMMARY
        •	∃ validation_status in {blocked, warning} → S4_VALIDATION_CORRECTION_LOOP
        """

        expected_files = {
            ft for ft, fid in self.ctx.file_record_id_map.items() if fid is not None
        }
        validated_files = set(self.ctx.validation_status_map.keys())

        # 1 还没全部 validate 完
        if validated_files < expected_files:
            next_file = sorted(expected_files - validated_files)[0]

            return TransitionDecision(
                next_state=self.ctx.current_state,
                action={
                    "type": "call_tool",
                    "tool_name": "validate_file_tool",
                    "args": {
                        "file_record_id": self.ctx.file_record_id_map[next_file]
                    }
                }
            )

        statuses = list(self.ctx.validation_status_map.values())
        
        # 2 全部 ok 或 confirmed → 生成 summary
        if all(status in {"ok", "confirmed"} for status in statuses):
            return TransitionDecision(
                next_state=CostCalcState.S5_GENERATE_COST_SUMMARY
            )
        # 3 存在 blocked 或 warning → 进入人工修正循环
        else:   
            return TransitionDecision(
                next_state=CostCalcState.S4_VALIDATION_CORRECTION_LOOP
            )

# -----------------------------S5_GENERATE_COST_SUMMARY handler ---------------------------------------------- 
    def _generate_cost_summary_s5(self, result: ToolResult) -> None:
        if result.tool_name == "generate_cost_summary_tool":
            if result.ok and result.data:
                cost_summary_id = result.data.get("id")
                if cost_summary_id:
                    self.ctx.cost_summary_id = cost_summary_id
    
    
    def _handle_s5(self) -> TransitionDecision:
        if not self.ctx.cost_summary_id:
            return TransitionDecision(
                next_state=self.ctx.current_state,
                action={
                    "type": "call_tool",
                    "tool_name": "generate_cost_summary_tool",
                    "args":{
                        "project_id": self.ctx.project_id,
                        "material_file_id": self.ctx.file_record_id_map.get("material_cost"),
                        "part_file_id": self.ctx.file_record_id_map.get("part_cost"),
                        "labor_file_id": self.ctx.file_record_id_map.get("labor_cost"),
                        "logistics_file_id": self.ctx.file_record_id_map.get("logistics_cost"),
                        "operator_id": self.ctx.agent_run_id,#如果没有operator_id，默认用system
                    }
                }
            )
        return TransitionDecision(
            next_state=CostCalcState.S6_GENERATE_COST_REPORT
        )

# -----------------------------S6_GENERATE_COST_REPORT handler ---------------------------------------------- 


if __name__ == "__main__":
   pass