# app/agentic/fsm/FSMContect.py
#FSM持久化context

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.agentic.fsm.enums import CostCalcState
from app.agentic.schemas.dto.validate_report_dto import ValidationReportDTO
from app.agentic.schemas.error_type import ErrorType


class FSMContext(BaseModel):

    '''
    FSM运行时的控制平面，是一个基于当前上下文，对下一步系统行为做确定性裁决的控制核心。
    
    需要包含以下几种类型的功能：
    1.agent_run实例的身份层(Agent Run Identity Layer)：如agent_run_id
    2.状态控制层(State Control Layer)：current_state,retry_count,max_retry等
    3.执行追踪层(Execution Trace Layer)：last_tool,last_error_type,context_snapshot_id等，让FSM的决策时感知上一个动作
    4.输入门控层(Input Gate Layer):required_inputs,collected_inputs等，输入控制收敛器，保证该状态的input 能够对齐required_inputs.实现系统与状态在输入环节的对齐。
    5.上下文快照层（Recovery Layer）:context_snapshot_id等，为回滚，replay，audit,失败恢复埋钩子。
    '''
    # 核心身份信息
    agent_run_id: str
    current_state: CostCalcState
    # ===============================
    # Retry & Error
    retry_count: int = 0
    last_error_type: Optional[ErrorType] = None
    last_tool: Optional[str] = None
    last_tool_ok: Optional[bool] = None
    # ===============================
    # 输入门控相关s1
    project_info: Dict[str, Any] = Field(default_factory=dict)
    confirmed_rawfile_id_map: Dict[str, Optional[str]]= Field(default_factory=dict)
    required_inputs: list[str] = Field(default_factory=list)
    #S1rawfile状态确认字典，{“material_cost”: None | “rawfile_id”...}
    
    # ===============================
    # 项目 & 文件 & 业务裁决缓存（关键）
    project_id: Optional[str] = None
    #s2_create_project状态成功后会有project_id，更新进来
    file_record_id_map:Dict[str, Optional[str]] = Field(default_factory=dict)
    #s2 upload_create_filerecord状态的文件上传结果，filerecord创建成功后会有id，更新进来。{“material_cost”: None | filerecord_id...}
    parse_status_map: Dict[str, str] = Field(default_factory=dict)
    #s3 parse_file的文件解析结果，{“material_cost”: filerecord.parse_status.value...}
    validation_status_map: Dict[str, str] = Field(default_factory=dict)
    #s4 validation_Correction_Loop的文件校验结果，{“material_cost”: filerecord.validation_status.value...}
    validation_reports: Dict[str, ValidationReportDTO] = Field(default_factory=dict)
    #s4 validate_Correction_Loop的文件校验报告，{“material_cost”: ValidationReport...}
    cost_summary_id: Optional[str] = None
    #s6 generate_cost_summary状态成功后会有cost_summary_id
    # ===============================
    # WAIT / Resume 支持
    pause_reason: Optional[str] = None
    # ===============================
    # 审计
    context_snapshot_id: Optional[str] = None
    last_transition_from: Optional[CostCalcState] = None
    last_transition_to: Optional[CostCalcState] = None
    # ===============================
    
    #max_retry
    @property
    def max_retry(self) -> int:
        return FSM_MAX_RETRY.get(self.current_state, 0)
    
    
    #global FSM setting
FSM_MAX_RETRY = {
    CostCalcState.S0_INIT: 1,
    CostCalcState.S1_INPUT_GATE: 2,
    CostCalcState.S2_CREATE_PROJECT: 2,
    CostCalcState.S3_PARSE_FILES: 3,
    CostCalcState.S4_VALIDATION_CORRECTION_LOOP: 0,#人工循环不自动重试
    CostCalcState.S5_GENERATE_COST_SUMMARY: 2,
    CostCalcState.S6_GENERATE_COST_REPORT: 2,
    CostCalcState.S7_PUBLISH_AND_SUMMARIZE: 2,
    CostCalcState.S8_DONE: 0,
    CostCalcState.S_WAIT_USER: 0,
    CostCalcState.S_ERR_ESCALATE: 0,
    }