import os
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

def test_generate_cost_summary_direct():
    from app.db.session import get_session
    from app.agentic.tools.generate_cost_summary_tool import generate_cost_summary_tool
    from app.db.auto_init import auto_init 
    
    auto_init()
    db = get_session()

    result = generate_cost_summary_tool(
        db=db,
        project_id="d1ede5f1-72aa-4c95-88f1-095c06c8c281",
        material_file_id="887b1932-58ce-4204-bf68-72989f7a08cd",
        part_file_id="f01a2249-d60c-4dea-b36c-9a64d9288430",
        labor_file_id="230d7198-e18a-4c60-8e79-26336e7477cc",
        logistics_file_id="dd9bccee-acca-4c44-b84f-5bd254920dbb",
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
        tool_name="generate_cost_summary",
        args={"db": db,
              "project_id": "d1ede5f1-72aa-4c95-88f1-095c06c8c281",
              "material_file_id": "887b1932-58ce-4204-bf68-72989f7a08cd",
              "part_file_id": "f01a2249-d60c-4dea-b36c-9a64d9288430",
              "labor_file_id": "230d7198-e18a-4c60-8e79-26336e7477cc",
              "logistics_file_id": "dd9bccee-acca-4c44-b84f-5bd254920dbb",
              "operator_id": "Agent"},
        allowlist={"generate_cost_summary"}
    )

    print(result.model_dump())

if __name__ == "__main__":
    test_generate_cost_summary_direct()
    test_executor_layer()