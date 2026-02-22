# app/agentic/tools/registry.py
from typing import Dict, Optional
from app.agentic.schemas.tool_spec import ToolSpec

class ToolRegistry:
    _instance_created = False#生产环境Guard
    
    def __init__(self):
        # 生产环境中,若已有全局实例，则不允许直接实例化，必须使用单一的全局的 tool_registry 实例
        if ToolRegistry._instance_created:
            raise RuntimeError("Use global tool_registry, do not instantiate ToolRegistry")
        ToolRegistry._instance_created = True
        
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        '''
        Register a new tool specification.
        Raises ValueError if a tool with the same name is already registered.
        
        param:
        spec: ToolSpec - The tool specification to register.
        '''
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        '''
        Get the tool specification by name.
        param:
        name: str - The name of the tool to retrieve.
        '''
        return self._tools.get(name)

# 全局唯一实例，import的时候自动初始化
tool_registry = ToolRegistry()