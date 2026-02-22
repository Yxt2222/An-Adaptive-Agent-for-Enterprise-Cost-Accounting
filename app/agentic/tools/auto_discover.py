# app/agentic/tools/auto_discover.py
import pkgutil
import importlib
import app.agentic.tools
#自动import app.agentic.tools 包下的所有模块，触发工具注册逻辑
'''
Agent/App启动时：

from app.agentic.tools.registry import tool_registry#先import模块注册实例，在导入全局tool_registry实例

from app.agentic.tools.auto_discover import discover_tools
discover_tools()# 这行代码会自动导入 app.agentic.tools 包下的所有模块，触发工具注册逻辑，把工具注册到全局的 tool_registry 中。


tool_registry.get("tool_name") # 现在可以拿到工具规范 
'''
def discover_tools():
    for _, module_name, _ in pkgutil.walk_packages(
        app.agentic.tools.__path__,
        app.agentic.tools.__name__ + "."
    ):
        importlib.import_module(module_name)