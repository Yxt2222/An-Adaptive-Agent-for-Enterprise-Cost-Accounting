# app/agentic/orchestration/semantic_guard.py
class SemanticGuard:
    def allowed_tools(self, state: str) -> set[str]:
        '''
        Get the set of allowed tool names set based on the current state.
        param:
        state: str - The current state of the orchestrator.
        '''
        if state == "ACT":
            return set()
        if state == "INIT":
            return {"ping"}   # MVP：先只放一个
        return set()
