from app.agentic.execution.tool_registry import ToolRegistry, ToolSpec
from app.agentic.execution.executor import PythonExecutor
from app.agentic.orchestration.semantic_guard import SemanticGuard
from app.agentic.orchestration.trace import TraceRecorder
from app.agentic.orchestration.orchestrator import Orchestrator
from app.agentic.tools.generate_cost_summary_tool import generate_cost_summary_tool
from app.agentic.schemas.risk_profile import ToolRiskProfile
def run_mvp(): 
    registry = ToolRegistry()# 1. register a tool registrier
    registry.register(ToolSpec(name="generate_cost_summary", 
                               func=generate_cost_summary_tool, 
                               description="generate cost summary tool",
                               input_schema={'text': str},
                               output_schema= 'echo' ,
                               risk_profile=ToolRiskProfile(modifies_persistent_data=False,
                                                            irreversible=False,
                                                            deletes_data=False,
                                                            affects_multiple_records=False)
                               ))# 2. register core tool(s)

    executor = PythonExecutor(registry)# 3. create executor with the tool registry
    guard = SemanticGuard()# 4. create semantic guard
    trace = TraceRecorder()# 5. create trace recorder

    orch = Orchestrator(executor=executor, guard=guard, trace=trace)# 6. create orchestrator
    orch.run()#run the orchestrator

if __name__ == "__main__":
    run_mvp()
