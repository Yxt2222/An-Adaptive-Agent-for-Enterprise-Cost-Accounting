#app/agentic/tests/test_validate_file_tool.py
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

def test_create_upload_file_direct():
    from app.db.session import get_session
    from app.agentic.tools.create_upload_file_record_tool import create_update_file_record_tool
    from app.db.auto_init import auto_init 
    
    auto_init()
    db = get_session()

    result = create_update_file_record_tool(
        db=db,
        project_id="1e189ac5-e375-467a-b37c-3fc4b5918f0f",
        file_type="material",
        storage_path="C:/Users/Yu/Desktop/项目/小微机械制造企业信息化，数字化转型/科利特数据/针梁式栈桥加工成本表（test）.xlsx",
        original_name="针梁式栈桥材料成本表（test）.xlsx",
        operator_id="Agent"
    )
    db.close()
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
        tool_name="create_update_file_record_tool",
        args={"db": db,
              "project_id": "1e189ac5-e375-467a-b37c-3fc4b5918f0f",
              "file_type": "material",
              "storage_path": "C:/Users/Yu/Desktop/项目/小微机械制造企业信息化，数字化转型/科利特数据/针梁式栈桥加工成本表（test）.xlsx",
              "original_name": "针梁式栈桥材料成本表（test）.xlsx",
              "operator_id": "Agent"},
        allowlist={"create_update_file_record"}
    )
    db.close()

    print(result.model_dump())
  
if __name__ == "__main__":
    test_create_upload_file_direct()
    test_executor_layer()