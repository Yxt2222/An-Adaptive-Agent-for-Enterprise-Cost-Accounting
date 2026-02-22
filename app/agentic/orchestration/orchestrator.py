# app/agentic/orchestration/orchestrator.py
from typing import Dict, Any
from app.agentic.orchestration.semantic_guard import SemanticGuard
from app.agentic.orchestration.trace import TraceRecorder
from app.agentic.execution.executor import PythonExecutor

class Orchestrator:
    def __init__(self, executor: PythonExecutor, guard: SemanticGuard, trace: TraceRecorder):
        self.executor = executor
        self.guard = guard
        self.trace = trace
        self.state = "INIT"
        self.memory: Dict[str, Any] = {}
        self.env_return: Dict[str, Any] = {}

    def run(self):
        '''
        Run the orchestration process.
        '''
        self.trace.emit("state_enter", state=self.state)
        
        #---------LLM模块-----------
        
        #--------------------------

        # --- MVP: INIT -> ACT (先不调用 LLM，直接进入可行动状态)
        self.state = "ACT"
        self.trace.emit("state_transition", from_state="INIT", to_state="ACT", by="orchestrator")
        self.trace.emit("state_enter", state=self.state)

        allowlist = self.guard.allowed_tools(self.state)
        self.trace.emit("allowed_tools", state=self.state, allowlist=sorted(list(allowlist)))

        # --- MVP: mock 一个 LLM tool_call
        tool_call = {"tool_name": "ping", "args": {"text": "hello"}}
        self.trace.emit("tool_call_received", tool_call=tool_call)
        #execute tool
        result = self.executor.execute(
            tool_name=tool_call["tool_name"],
            args=tool_call["args"],
            allowlist=allowlist
        )
        self.env_return = result
        self.trace.emit("tool_executed", result=result)

        # --- done
        self.state = "DONE"
        self.trace.emit("state_transition", from_state="ACT", to_state="DONE", by="orchestrator")
        self.trace.emit("run_end", final_state=self.state)
        self.trace.dump()
