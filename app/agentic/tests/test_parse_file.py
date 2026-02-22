#app/agentic/tests/test_validate_file_tool.py
import os
from app.agentic.tools.auto_discover import discover_tools
from app.db.session import get_engine
#数据库路径设置为工作目录
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///./cost_sys.db"
)
#查看当前工作路径current working directory
engine = get_engine()
print("CWD =", os.getcwd())
print("ENGINE URL =", engine.url)

def test_parse_file_direct():
    from app.db.session import get_session
    from app.agentic.tools.parse_file_tool import parse_file_tool
    from app.db.auto_init import auto_init 
    
    auto_init()
    db = get_session()

    result = parse_file_tool(
        db=db,
        file_id="a844db10-8a66-42e5-bfc7-cd60964af38f",
        operator_id="Agent"
    )
    print(result.model_dump())

def test_executor_layer():
    from app.agentic.execution.executor import PythonExecutor
    from app.db.session import get_session
    from app.db.auto_init import auto_init 
    
    from app.agentic.tools.registry import tool_registry#导入全局的 tool_registry 实例
    from app.agentic.tools.auto_discover import discover_tools
    discover_tools()#注册tool_registry并加入工具。
    
    
    
    executor = PythonExecutor(tool_registry)
    
    auto_init()
    db = get_session()
    result = executor.execute(
        tool_name="parse_file",
        args={"db": db,
              "file_id": "a844db10-8a66-42e5-bfc7-cd60964af38f",
              "operator_id": "Agent"},
        allowlist={"parse_file"}
    )
  
    print(result.model_dump())

if __name__ == "__main__":
    test_parse_file_direct()
    test_executor_layer()