"""
Semantic Infrastructure 完整流程演示
演示从 Schema 定义到 SemanticObject 生成的完整流水线
"""
import uuid
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.agentic.semantic_infra import SemanticInfrastructureService

# ==============================
# 第1步：定义 ToolSpec Schema (Pydantic 模型)
# ==============================
class ToolSpec(BaseModel):
    """工具描述范本定义 - 用于描述 Agent 可调用的工具"""
    name: str = Field(..., description="工具名称，如 'calculator'")
    description: str = Field(..., description="工具功能的自然语言描述")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="工具输入参数定义")
    requires_context: bool = Field(default=False, description="是否需要运行时上下文")
    category: Optional[str] = Field(None, description="工具分类")

# ==============================
# 第2步：初始化 SemanticInfrastructureService 并注册 Schema
# ==============================
service = SemanticInfrastructureService()

# 注册 ToolSpec Schema
schema_version = service.register_schema(
    schema_model=ToolSpec,
    name="ToolSpec",
    version="v1.0.0",
    author="system",
    description="工具调用的标准 Schema"
)

print("=" * 60)
print("[Schema] Schema 注册成功")
print("=" * 60)
print(f"Schema 名称: ToolSpec")
print(f"Schema 版本: {schema_version}")
print()

# 验证 Schema 已注册
retrieved_schema = service.get_schema("ToolSpec", "v1.0.0")
print("[Schema] 注册的 Schema 内容:")
print(f"  - name: {retrieved_schema.name}")
print(f"  - fields: {list(retrieved_schema.fields.keys())}")
print(f"  - required_fields: {retrieved_schema.required_fields}")
print(f"  - description: {retrieved_schema.description}")
print(f"  - version_id: {retrieved_schema.version_id}")
print()

# ==============================
# 第3步：定义 Template Object (field_rules)
# ==============================
def format_description_rule(standardized: Dict[str, Any]) -> str:
    """转换规则：格式化 description，添加工具分类前缀"""
    name = standardized.get('name', 'Unknown')
    desc = standardized.get('description', '')
    category = standardized.get('category', 'General')
    return f"[{category}] {name}: {desc}"

def enhance_parameters_rule(standardized: Dict[str, Any]) -> Dict[str, Any]:
    """转换规则：增强参数信息，添加默认值说明"""
    params = standardized.get('parameters', {})
    enhanced = {
        **params,
        "enhanced": True,
        "enhanced_at": "transform_time"
    }
    return enhanced

# 定义 field_rules
field_rules = {
    "description": format_description_rule,      # callable 转换函数
    "parameters": enhance_parameters_rule,       # callable 转换函数
    "category": "system_assigned",               # 字符串规则（标记）
}

print("=" * 60)
print("[Template] Template field_rules 定义")
print("=" * 60)
print(f"  - description: {format_description_rule.__name__} (callable)")
print(f"  - parameters: {enhance_parameters_rule.__name__} (callable)")
print(f"  - category: 'system_assigned' (string rule)")
print()

# ==============================
# 第4步：注册 Template Object
# ==============================
template_version = service.register_template(
    template_dict=field_rules,
    template_name="ToolSpecTemplate",
    version="v1.0.0",
    author="system",
    description="ToolSpec 的转换模板，格式化描述和增强参数"
)

print("=" * 60)
print("[Template] Template 注册成功")
print("=" * 60)
print(f"Template 名称: ToolSpecTemplate")
print(f"Template 版本: {template_version}")
print()

# 验证 Template 已注册
retrieved_template = service.get_template("ToolSpecTemplate", "v1.0.0")
print("[Template] 注册的 Template 内容:")
print(f"  - template_name: {retrieved_template.template_name}")
print(f"  - field_rules keys: {list(retrieved_template.field_rules.keys())}")
print(f"  - description: {retrieved_template.description}")
print(f"  - version_id: {retrieved_template.version_id}")
print()

# ==============================
# 第5步：创建 SchemaInstance (实例化一个 ToolSpec 对象)
# ==============================
field_values = {
    "name": "price_calculator",
    "description": "计算商品总价，支持折扣计算",
    "parameters": {
        "price": {"type": "float", "description": "单价"},
        "quantity": {"type": "int", "description": "数量"},
        "discount": {"type": "float", "description": "折扣率", "default": 1.0}
    },
    "requires_context": True,
    "category": "Pricing"
}

instance_name = service.register_instance(
    schema_name="ToolSpec",
    schema_version="v1.0.0",
    field_values=field_values,
    instance_name="PriceCalculator_Instance_001",
    description="价格计算器实例 - 用于批量编辑场景",
    created_by="system"
)

print("=" * 60)
print("[Instance] SchemaInstance 注册成功")
print("=" * 60)
print(f"Instance 名称: {instance_name}")
print(f"Schema: ToolSpec v1.0.0")
print(f"[Instance] 字段值:")
print(f"  - name: {field_values['name']}")
print(f"  - description: {field_values['description']}")
print(f"  - parameters keys: {list(field_values['parameters'].keys())}")
print(f"  - requires_context: {field_values['requires_context']}")
print(f"  - category: {field_values['category']}")
print()

# 验证 Instance 已注册
retrieved_instance = service.get_instance("PriceCalculator_Instance_001")
if retrieved_instance:
    print("[Instance] 从数据库获取的实例:")
    print(f"  - name: {retrieved_instance.name}")
    print(f"  - schema_name: {retrieved_instance.schema_name}")
    print(f"  - schema_version: {retrieved_instance.schema_version}")
    print(f"  - description: {retrieved_instance.description}")
    print(f"  - field_values keys: {list(retrieved_instance.field_values.keys())}")
else:
    print("[Instance] 未找到实例 'PriceCalculator_Instance_001'")
print()

# 列出所有实例
all_instances = service.list_instances(schema_name="ToolSpec")
print(f"[List] ToolSpec 下的所有实例 (共 {len(all_instances)} 个):")
for inst in all_instances:
    print(f"  - {inst.name}: {inst.description}")
print()

# ==============================
# 第6步：应用 transform_description (从原始 Pydantic 对象)
# ==============================
tool_spec_instance = ToolSpec(
    name="price_calculator",
    description="计算商品总价，支持折扣计算",
    parameters={
        "price": {"type": "float", "description": "单价"},
        "quantity": {"type": "int", "description": "数量"},
        "discount": {"type": "float", "description": "折扣率", "default": 1.0}
    },
    requires_context=True,
    category="Pricing"
)

agent_run_id = "run_20250314_001"

semantic_obj1 = service.transform_description(
    agent_run_id=agent_run_id,
    obj=tool_spec_instance,
    schema_name="ToolSpec",
    schema_version="v1.0.0",
    template_name="ToolSpecTemplate",
    template_version="v1.0.0"
)

print("=" * 60)
print("[Transform] transform_description 执行完成")
print("=" * 60)
print(f"[ID] agent_run_id: {semantic_obj1.agent_run_id}")
print(f"[Name] object_name: {semantic_obj1.object_name}")
print(f"[SchemaVer] schema_version: {semantic_obj1.schema_version}")
print(f"[TemplateVer] template_version: {semantic_obj1.template_version}")
print(f"[Time] timestamp: {semantic_obj1.timestamp}")
print()
print("[Fields] standardized_fields (转换后的字段):")
print("-" * 60)
for key, value in semantic_obj1.standardized_fields.items():
    if isinstance(value, dict):
        print(f"  {key}:")
        for k, v in value.items():
            print(f"      {k}: {v}")
    else:
        print(f"  {key}: {value}")
print()

# ==============================
# 第7步：应用 transform_from_instance (从已注册的实例 - 优化路径)
# ==============================
if retrieved_instance:
    semantic_obj2 = service.transform_from_instance(
        agent_run_id=agent_run_id,
        instance=retrieved_instance,
        template_name="ToolSpecTemplate",
        template_version="v1.0.0"
    )

    print("=" * 60)
    print("[Transform] transform_from_instance 执行完成 (优化路径)")
    print("=" * 60)
    print(f"[ID] agent_run_id: {semantic_obj2.agent_run_id}")
    print(f"[Name] object_name: {semantic_obj2.object_name}")
    print(f"[SchemaVer] schema_version: {semantic_obj2.schema_version}")
    print(f"[TemplateVer] template_version: {semantic_obj2.template_version}")
    print(f"[Time] timestamp: {semantic_obj2.timestamp}")
    print()
    print("[Fields] standardized_fields (转换后的字段):")
    print("-" * 60)
    for key, value in semantic_obj2.standardized_fields.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"      {k}: {v}")
        else:
            print(f"  {key}: {value}")
    print()

# ==============================
# 对比：转换前 vs 转换后 (仅在有实例时)
# ==============================
if retrieved_instance:
    print("=" * 60)
    print("[Transform] 转换前后对比")
    print("=" * 60)
    print("\n[转换前 - 原始数据]")
    print(f"  description: {tool_spec_instance.description}")
    print(f"  parameters keys: {list(tool_spec_instance.parameters.keys())}")
    print(f"  category: {tool_spec_instance.category}")
    print()
    print("\n[转换后 - SemanticObject]")
    print(f"  description: {semantic_obj2.standardized_fields['description']}")
    print(f"  parameters keys: {list(semantic_obj2.standardized_fields['parameters'].keys())}")
    print(f"  category: {semantic_obj2.standardized_fields['category']}")
    print()

    # 展示 Template 的效果
    print("=" * 60)
    print("[Effect] Template 转换效果说明")
    print("=" * 60)
    print("1. description 字段: 被 format_description_rule 函数转换")
    print(f"   原始: '{tool_spec_instance.description}'")
    print(f"   转换后: '{semantic_obj2.standardized_fields['description']}'")
    print()
    print("2. parameters 字段: 被 enhance_parameters_rule 函数增强")
    print("   原始: 只包含 price, quantity, discount")
    print("   转换后: 新增 enhanced=True 和 enhanced_at='transform_time'")
    print()
    print("3. category 字段: 字符串规则 'system_assigned'")
    print("   原始: 'Pricing'")
    print("   转换后: 保持原值 (字符串规则仅作标记，不修改数据)")
    print()

# ==============================
# 验证 SemanticObject 符合 Schema
# ==============================
print("=" * 60)
print("[Validate] 验证 SemanticObject 符合 Schema")
print("=" * 60)

# 验证 transform_description 的结果
is_valid1 = service.validate(
    obj=semantic_obj1.standardized_fields,
    schema_name="ToolSpec",
    version="v1.0.0"
)
print(f"transform_description 结果是否符合 Schema: {is_valid1}")

# 验证 transform_from_instance 的结果
is_valid2 = service.validate(
    obj=semantic_obj2.standardized_fields,
    schema_name="ToolSpec",
    version="v1.0.0"
)
print(f"transform_from_instance 结果是否符合 Schema: {is_valid2}")
print()

# ==============================
# 查询历史 SemanticObject
# ==============================
print("=" * 60)
print("[History] 查询历史 SemanticObject")
print("=" * 60)

# 查询特定 Agent 运行的所有语义对象
history_results = service.query_historical_semantics(
    agentic_run_id=agent_run_id
)
print(f"[查询] Agent 运行 ID '{agent_run_id}' 的所有语义对象 (共 {len(history_results)} 个):")
for obj in history_results:
    print(f"  - {obj.object_name} @ {obj.timestamp}")
print()

# 查询特定 Schema 的所有语义对象
schema_history = service.query_historical_semantics(
    schema_name="ToolSpec"
)
print(f"[查询] Schema 'ToolSpec' 的所有语义对象 (共 {len(schema_history)} 个):")
for obj in schema_history[:5]:  # 只显示前5个
    print(f"  - {obj.object_name} @ {obj.timestamp}")
if len(schema_history) > 5:
    print(f"  ... 还有 {len(schema_history) - 5} 个")
print()

# ==============================
# 查看变更日志
# ==============================
print("=" * 60)
print("[ChangeLog] 变更日志")
print("=" * 60)
print(f"[查询] 最近的变更日志 (最多 10 条):")
change_log = service.get_change_log(limit=10)
for record in change_log:
    print(f"  [{record.timestamp}] {record.operator} - {record.change_description}")
    print(f"    对象: {record.object_name}, 版本: {record.version_id}")
print()

# ==============================
# 总结
# ==============================
print("=" * 60)
print("[Summary] 测试总结")
print("=" * 60)
print("完成的测试步骤:")
print("  1. 注册 Schema (ToolSpec)")
print("  2. 注册 Template (ToolSpecTemplate)")
print("  3. 创建 SchemaInstance (PriceCalculator_Instance_001)")
print("  4. transform_description - 从原始对象转换")
print("  5. transform_from_instance - 从已注册实例转换 (优化)")
print("  6. 验证转换结果")
print("  7. 查询历史 SemanticObject")
print("  8. 查看变更日志")
print()
print("存储验证:")
print("  - Schema/Template: JSON 文件持久化")
print("  - SchemaInstance/SemanticObject/ChangeRecord: 数据库持久化")
print()
print("=" * 60)
print("测试完成！")
print("=" * 60)
