# app/agentic/fsm/Transition.py
#状态决策结果

from typing import Optional
from pydantic import BaseModel
from app.agentic.fsm.enums import CostCalcState

class TransitionDecision(BaseModel):
    """
    当前状态执行后的裁决结果。
    这是 FSM 与外部执行环境解耦的关键协议。
    """

    next_state: CostCalcState
    pause: bool = False

    # 新增：FSM是否请求调用某个工具
    action: Optional[dict] = None
    