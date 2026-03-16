# app/agentic/semantic_infra.py
import json
import uuid
import copy
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Type, List, Optional, Union

from pydantic import BaseModel, ValidationError,create_model

from app.db.session import get_session
from app.models.Semantic_infra_related_models import (
    SchemaInstanceModel,
    ChangeRecordModel,
    SemanticObjectModel
)

# ---------------------------
# 存储配置
# ---------------------------

# JSON 存储目录路径
_SEMANTIC_STORAGE_DIR = Path(__file__).parent.parent.parent / "semantic_storage"
_SCHEMAS_JSON_PATH = _SEMANTIC_STORAGE_DIR / "schemas.json"
_TEMPLATES_JSON_PATH = _SEMANTIC_STORAGE_DIR / "templates.json"

# 确保存储目录存在
_SEMANTIC_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------
# JSON 存储工具函数
# ---------------------------

def _load_json_storage(path: Path) -> dict:
    """从 JSON 文件加载数据"""
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_json_storage(path: Path, data: dict):
    """保存数据到 JSON 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


# ---------------------------
# 类型序列化工具
# ---------------------------

# 类型名称到类型对象的映射（用于 JSON 反序列化）
_TYPE_REGISTRY: Dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
    "Any": Any,
}


def _serialize_type(field_type: Any) -> str:
    """将 Python 类型对象序列化为字符串"""
    if field_type is Any:
        return "Any"
    # 获取类型名称
    type_name = getattr(field_type, "__name__", str(field_type))
    # 处理泛型类型（如 List[int], Dict[str, int]）
    if hasattr(field_type, "__origin__"):
        origin = field_type.__origin__
        origin_name = getattr(origin, "__name__", str(origin))
        if hasattr(field_type, "__args__"):
            args_str = ", ".join(_serialize_type(arg) for arg in field_type.__args__)
            return f"{origin_name}[{args_str}]"
    return type_name


def _deserialize_type(type_str: str) -> Any:
    """将类型字符串反序列化为 Python 类型对象"""
    # 处理 Optional 类型
    if type_str.startswith("Optional[") and type_str.endswith("]"):
        inner_type_str = type_str[9:-1]
        inner_type = _deserialize_type(inner_type_str)
        return Optional[inner_type]

    # 处理 Union 类型
    if type_str.startswith("Union[") and type_str.endswith("]"):
        inner_types_str = type_str[6:-1]
        # 处理多个类型，如 "Union[str, int, None]"
        inner_types = [
            _deserialize_type(t.strip())
            for t in inner_types_str.split(",")
        ]
        return Union[tuple(inner_types)]

    # 处理 List 类型
    if type_str.startswith("List[") and type_str.endswith("]"):
        inner_type_str = type_str[5:-1]
        inner_type = _deserialize_type(inner_type_str)
        return List[inner_type]

    # 处理 Dict 类型
    if type_str.startswith("Dict[") and type_str.endswith("]"):
        parts = type_str[5:-1].split(",", 1)
        if len(parts) == 2:
            key_type = _deserialize_type(parts[0].strip())
            value_type = _deserialize_type(parts[1].strip())
            return Dict[key_type, value_type]

    # 从注册表中查找简单类型
    return _TYPE_REGISTRY.get(type_str, Any)


def _serialize_fields(fields: Dict[str, type]) -> Dict[str, str]:
    """将字段类型字典序列化为字符串字典"""
    return {k: _serialize_type(v) for k, v in fields.items()}


def _deserialize_fields(fields_str: Dict[str, str]) -> Dict[str, type]:
    """将字段类型字符串字典反序列化为类型字典"""
    return {k: _deserialize_type(v) for k, v in fields_str.items()}


# ---------------------------
# 核心对象定义
# ---------------------------

class SchemaObject(BaseModel):
    """系统中所有参与 Agent 推理或裁决的数据结构"""

    name: str
    fields: Dict[str, Any]  # 字段类型，可以是简单类型（str, int）或复杂类型（Optional[str], List[int] 等）
    description: Optional[str] = None
    required_fields: Optional[List[str]] = None
    constraints: Optional[Dict[str, Any]] = None
    version_id: Optional[str] = None

    def to_pydantic_model(self) -> Type[BaseModel]:
        """
        将 SchemaObject 转换为一个动态 Pydantic Model
        """

        field_definitions = {}

        for field_name, field_type in self.fields.items():

            if self.required_fields and field_name in self.required_fields:
                field_definitions[field_name] = (field_type, ...)
            else:
                field_definitions[field_name] = (Optional[field_type], None)

        model = create_model(
            self.name,
            **field_definitions
        )

        return model

    def validate(self, obj: Dict[str, Any]) -> bool:
        """
        使用 Pydantic Model 进行验证
        """

        try:
            Model = self.to_pydantic_model()
            Model.model_validate(obj)
            return True

        except ValidationError as e:
            print(f"Semantic validation error: {e}")
            return False
        
    def model_validate(self, obj: Dict[str, Any]) -> BaseModel:
        Model = self.to_pydantic_model()
        return Model.model_validate(obj)
            

class TemplateObject(BaseModel):
    '''定义模板规则'''
    template_name: str#模板名称
    field_rules: Dict[str, Any]  # 字段规则，可存 callable 或字符串描述规则
    description: Optional[str] = None#可选描述
    version_id: Optional[str] = None#版本号，可选，默认为注册时间戳

class SemanticObject(BaseModel):
    """经过 Transformer 转换的 Agent-ready 输入对象"""
    agent_run_id: str#Agent 运行 ID
    object_name: str#对象名称，如 "BatchEditItemsInput"
    standardized_fields: Dict[str, Any]#标准化字段
    schema_name: Optional[str] = None#所属 Schema 名称
    schema_version: Optional[str] = None#schema 版本
    template_name: Optional[str] = None#所属 Template 名称
    template_version: Optional[str] = None#模板版本
    timestamp: datetime#时间戳

class SchemaInstance(BaseModel):
    '''SchemaObject的实例，包含具体语义值'''
    name :str#实例名称，如 "BatchEditItemsInput_Instance1"
    schema_name: str#所属Schema名称
    schema_version: Optional[str] = None#所属Schema版本
    field_values: Dict[str, Any]#字段值，key为字段名，value为具体值
    description: Optional[str] = None#可选描述

class ChangeRecord(BaseModel):
    object_name: str#对象名称
    version_id: str#版本号
    operator: str#操作者
    timestamp: datetime#时间戳
    change_description: str#变更描述

# ---------------------------
# Semantic Infrastructure 主类
# ---------------------------

class SemanticInfrastructureService:
    """
    语义基础设施服务
    - SchemaObject 和 TemplateObject 使用 JSON 持久化
    - SchemaInstance 使用 SQLAlchemy 持久化
    """
    def __init__(self):
        # 内存缓存（启动时从 JSON 加载）
        self.schema_registry: Dict[str, Dict[str, SchemaObject]] = {}
        self.template_registry: Dict[str, Dict[str, TemplateObject]] = {}

        # 从 JSON 加载现有数据
        self._load_from_json()

    # -----------------------
    # JSON 持久化方法
    # -----------------------

    def _load_from_json(self):
        """从 JSON 文件加载 Schema 和 Template"""
        # 加载 Schemas
        schemas_data = _load_json_storage(_SCHEMAS_JSON_PATH)
        for name, versions in schemas_data.items():
            self.schema_registry[name] = {}
            for version, data in versions.items():
                # 反序列化字段类型
                if "fields" in data and isinstance(data["fields"], dict):
                    data["fields"] = _deserialize_fields(data["fields"])
                self.schema_registry[name][version] = SchemaObject(**data)

        # 加载 Templates
        templates_data = _load_json_storage(_TEMPLATES_JSON_PATH)
        for name, versions in templates_data.items():
            self.template_registry[name] = {}
            for version, data in versions.items():
                self.template_registry[name][version] = TemplateObject(**data)

    def _log_change(self, object_name: str, version_id: str, operator: str, change_description: str):
        """
        记录变更日志到数据库

        Args:
            object_name: 对象名称
            version_id: 版本 ID
            operator: 操作者
            change_description: 变更描述
        """
        session = get_session()
        try:
            db_record = ChangeRecordModel(
                id=str(uuid.uuid4()),
                object_name=object_name,
                version_id=version_id,
                operator=operator,
                timestamp=datetime.now(),
                change_description=change_description
            )
            session.add(db_record)
            session.commit()
        except Exception as e:
            print(f"Failed to log change to database: {e}")
            session.rollback()
        finally:
            session.close()

    def _save_semantic_object_to_db(self, semantic_obj: SemanticObject):
        """
        将 SemanticObject 持久化到数据库

        Args:
            semantic_obj: SemanticObject 对象
        """
        session = get_session()
        try:
            db_record = SemanticObjectModel(
                id=str(uuid.uuid4()),
                agent_run_id=semantic_obj.agent_run_id,
                object_name=semantic_obj.object_name,
                standardized_fields=semantic_obj.standardized_fields,
                schema_name=semantic_obj.schema_name,
                schema_version=semantic_obj.schema_version,
                template_name=semantic_obj.template_name,
                template_version=semantic_obj.template_version,
                timestamp=semantic_obj.timestamp
            )
            session.add(db_record)
            session.commit()
        except Exception as e:
            print(f"Failed to save semantic object to database: {e}")
            session.rollback()
        finally:
            session.close()

    def _save_schemas_to_json(self):
        """保存 Schemas 到 JSON"""
        data = {}
        for name, versions in self.schema_registry.items():
            data[name] = {}
            for v, obj in versions.items():
                schema_dict = obj.model_dump()
                # 序列化字段类型
                if "fields" in schema_dict and isinstance(schema_dict["fields"], dict):
                    schema_dict["fields"] = _serialize_fields(schema_dict["fields"])
                data[name][v] = schema_dict
        _save_json_storage(_SCHEMAS_JSON_PATH, data)

    def _save_templates_to_json(self):
        """保存 Templates 到 JSON"""
        data = {}
        for name, versions in self.template_registry.items():
            data[name] = {v: obj.model_dump() for v, obj in versions.items()}
        _save_json_storage(_TEMPLATES_JSON_PATH, data)

    # -----------------------
    # Schema 方法
    # -----------------------

    def register_schema(self,
                        schema_model: Type[BaseModel],
                        name: str,
                        version: Optional[str]=None,
                        author: Optional[str]=None,
                        description: Optional[str]=None
                        )-> Optional[str]:
        '''
        功能: 注册一个 Schema 到注册表中
        流程:
        生成版本ID（传入或使用当前时间戳）
        从 Pydantic 模型提取字段
        创建 SchemaObject
        按名称+版本存储
        如果有作者，记录变更日志
        '''
        version = version or datetime.now().isoformat()
        # 检查版本是否已存在
        if version in self.schema_registry.get(name, {}):
            #raise ValueError(f"Schema {name} version {version} already exists")
            return None
        # 提取字段类型
        fields = {f: schema_model.model_fields[f].annotation for f in schema_model.model_fields}

        # 提取必填字段（is_required 为 True）
        required_fields = [
            f for f in schema_model.model_fields
            if schema_model.model_fields[f].is_required()
        ]

        schema_obj = SchemaObject(
            name=name,
            fields=fields,
            required_fields=required_fields if required_fields else None,
            description=description,
            version_id=version
        )

        self.schema_registry.setdefault(name, {})[version] = schema_obj
        self._save_schemas_to_json()  # 持久化到 JSON

        if author:
            self._log_change(name, version, author, "Register schema")
        return schema_obj.version_id

    def get_schema(self,
                    name: str,
                    version: Optional[str]=None) -> SchemaObject:
        '''
        功能: 获取指定名称和版本的 Schema
        逻辑:
        如果指定版本 → 返回指定版本
        如果未指定版本 → 返回最新版本（按排序后的最后一个）
        '''
        versions = self.schema_registry.get(name)
        if not versions:
            raise ValueError(f"Schema {name} not found")
        if version:
            schema = versions.get(version)
            if not schema:
                raise ValueError(f"Schema {name} version {version} not found")
            return schema
        # 默认返回最新版本
        latest_version = sorted(versions.keys())[-1]
        return versions[latest_version]

    def list_schemas(self, name: Optional[str] = None) -> Dict[str, List[str]]:
        """
        列出所有 Schema 或指定 Schema 的所有版本
        返回: {schema_name: [version1, version2, ...]}
        """
        if name:
            if name not in self.schema_registry:
                return {}
            return {name: sorted(self.schema_registry[name].keys())}
        return {n: sorted(v.keys()) for n, v in self.schema_registry.items()}

    # -----------------------
    # Template 方法
    # -----------------------

    def register_template(self,
                            template_dict: Dict[str, Any],
                            template_name: str,
                            version: Optional[str]=None,
                            author: Optional[str]=None,
                            description: Optional[str]=None
                            ) -> Optional[str]:
        '''
        功能: 注册一个 Template 到注册表中
        流程:
        生成版本ID
        创建 TemplateObject
        按名称+版本存储
        记录变更日志
        '''
        version = version or datetime.now().isoformat()
        template_obj = TemplateObject(
            template_name=template_name,
            field_rules=template_dict,
            description=description,
            version_id=version
        )
        self.template_registry.setdefault(template_name, {})[version] = template_obj
        self._save_templates_to_json()  # 持久化到 JSON

        if author:
            self._log_change(template_name, version, author, "Register template")
        return template_obj.version_id

    def get_template(self, template_name: str, version: Optional[str]=None) -> TemplateObject:
        versions = self.template_registry.get(template_name)
        if not versions:
            raise ValueError(f"Template {template_name} not found")
        if version:
            template = versions.get(version)
            if not template:
                raise ValueError(f"Template {template_name} version {version} not found")
            return template
        # 默认返回最新版本
        latest_version = sorted(versions.keys())[-1]
        return versions[latest_version]

    def list_templates(self, name: Optional[str] = None) -> Dict[str, List[str]]:
        """
        列出所有 Template 或指定 Template 的所有版本
        返回: {template_name: [version1, version2, ...]}
        """
        if name:
            if name not in self.template_registry:
                return {}
            return {name: sorted(self.template_registry[name].keys())}
        return {n: sorted(v.keys()) for n, v in self.template_registry.items()}

    # -----------------------
    # SchemaInstance 方法（数据库持久化）
    # -----------------------

    def register_instance(self,
                           schema_name: str,
                           schema_version: Optional[str],
                           field_values: Dict[str, Any],
                           instance_name: Optional[str] = None,
                           description: Optional[str] = None,
                           created_by: Optional[str] = None) -> str:
        """
        注册一个 SchemaInstance 到数据库

        Args:
            schema_name: 所属 Schema 名称
            schema_version: 所属 Schema 版本
            field_values: 字段值字典
            instance_name: 实例名称（如未提供，自动生成）
            description: 可选描述
            created_by: 创建者

        Returns:
            实例名称
        """
        # 验证 Schema 是否存在
        schema = self.get_schema(schema_name, schema_version)

        # 生成实例名称
        if not instance_name:
            instance_name = f"{schema_name}_{uuid.uuid4().hex[:8]}"

        # 验证字段值是否符合 Schema 定义
        if not schema.validate(field_values):
            raise ValueError(f"Field values do not match schema '{schema_name}'")

        # 创建数据库记录
        session = get_session()
        try:
            instance = SchemaInstanceModel(
                id=str(uuid.uuid4()),
                name=instance_name,
                schema_name=schema_name,
                schema_version=schema_version,
                field_values=field_values,
                description=description,
                created_by=created_by
            )
            session.add(instance)
            session.commit()
            session.refresh(instance)
            return instance.name
        finally:
            session.close()

    def get_instance(self,
                     name: str,
                     schema_name: Optional[str] = None,
                     schema_version: Optional[str] = None) -> Optional[SchemaInstance]:
        """
        获取已注册的 SchemaInstance

        Args:
            name: 实例名称
            schema_name: 可选，过滤 Schema 名称
            schema_version: 可选，过滤 Schema 版本

        Returns:
            SchemaInstance 对象
        """
        session = get_session()
        try:
            query = session.query(SchemaInstanceModel).filter(
                SchemaInstanceModel.name == name
            )

            if schema_name:
                query = query.filter(SchemaInstanceModel.schema_name == schema_name)
            if schema_version:
                query = query.filter(SchemaInstanceModel.schema_version == schema_version)

            db_instance = query.first()

            if not db_instance:
                return None

            return SchemaInstance(
                name=db_instance.name,
                schema_name=db_instance.schema_name,
                schema_version=db_instance.schema_version,
                field_values=db_instance.field_values,
                description=db_instance.description
            )
        finally:
            session.close()

    def list_instances(self,
                       schema_name: Optional[str] = None,
                       schema_version: Optional[str] = None) -> List[SchemaInstance]:
        """
        列出所有 给定所有Schema_name和Schema_version下的所有SchemaInstance

        Args:
            schema_name: 可选，过滤 Schema 名称
            schema_version: 可选，过滤 Schema 版本

        Returns:
            SchemaInstance 对象列表
        """
        session = get_session()
        try:
            query = session.query(SchemaInstanceModel)

            if schema_name:
                query = query.filter(SchemaInstanceModel.schema_name == schema_name)
            if schema_version:
                query = query.filter(SchemaInstanceModel.schema_version == schema_version)

            db_instances = query.all()

            return [
                SchemaInstance(
                    name=inst.name,
                    schema_name=inst.schema_name,
                    schema_version=inst.schema_version,
                    field_values=inst.field_values,
                    description=inst.description
                )
                for inst in db_instances
            ]
        finally:
            session.close()

    def delete_instance(self, name: str) -> bool:
        """
        删除一个 SchemaInstance

        Args:
            name: 实例名称

        Returns:
            是否删除成功
        """
        session = get_session()
        try:
            instance = session.query(SchemaInstanceModel).filter(
                SchemaInstanceModel.name == name
            ).first()

            if not instance:
                return False

            session.delete(instance)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # -----------------------
    # 验证方法
    # -----------------------

    def validate(self,
                    obj: Dict[str, Any],
                    schema_name: str,
                    version: Optional[str]=None) -> bool:
        '''
        功能: 验证对象是否符合指定 Schema
        逻辑:
        获取目标 Schema
        使用 SchemaObject 的 validate 方法进行验证
        '''
        schema = self.get_schema(schema_name, version)
        return schema.validate(obj)

    # -----------------------
    # Transformer 方法
    # -----------------------

    def transform_description(self,
                    agent_run_id: str,
                    obj: BaseModel,
                    schema_name: str,
                    schema_version: Optional[str]=None,
                    template_name: Optional[str]=None,
                    template_version: Optional[str]=None) -> SemanticObject:
        '''
        功能: 将不由Semantic_infra统一创建的描述性对象（AgentIdentity, StateTask, ToolSpec）转化为
        LLM-ready semantic object(SemanticObject)，并附带版本信息。
        流程:
        获取目标 Schema 和（可选的）Template
        按照 Schema 的字段标准化输入对象
        如果有 Template，应用其 field_rules，转换model到Agentic-ready输出：
        如果 rule 是可调用的 → 执行函数转换字段
        如果 rule 是字符串 → 作为标记保留字段
        返回包含版本信息的 SemanticObject
        '''
        # 1. 获取 schema
        schema_obj = self.get_schema(schema_name, schema_version)

        # 2. 获取 template（如果有）
        template_obj = None
        if template_name:
            template_obj = self.get_template(template_name, template_version)

        # 3. 标准化字段
        standardized = {}
        for field_name in schema_obj.fields.keys():
            value = getattr(obj, field_name, None)
            standardized[field_name] = value

        # 4. 应用模板规则（可选）
        if template_obj:
            for key, rule in template_obj.field_rules.items():
                if callable(rule):
                    standardized[key] = rule(standardized)
                #若 rule 是字符串 → 作为标记保留字段，不做处理
                elif isinstance(rule, str):
                    pass


        # 5. 构造 SemanticObject
        semantic_obj = SemanticObject(
            agent_run_id=agent_run_id,
            object_name=getattr(obj, "name", ""),
            standardized_fields=standardized,
            schema_name=schema_obj.name,
            schema_version=schema_obj.version_id,
            template_name=template_obj.template_name if template_obj else None,
            template_version=template_obj.version_id if template_obj else None,
            timestamp=datetime.now()
        )

        # 录入数据库
        self._save_semantic_object_to_db(semantic_obj)

        return semantic_obj

    def transform_from_instance(self,
                                 agent_run_id: str,
                                 instance: SchemaInstance,
                                 template_name: Optional[str]=None,
                                 template_version: Optional[str]=None) -> SemanticObject:
        """
        从已注册的 SchemaInstance 直接转换为 SemanticObject
        优化：跳过 schema 查询和字段遍历，直接使用 instance.field_values

        Args:
            agent_run_id: Agent 运行 ID
            instance: SchemaInstance 对象
            template_name: 可选模板名称
            template_version: 可选模板版本

        Returns:
            SemanticObject
        """
        # 获取模板（如果有）
        template_obj = None
        if template_name:
            template_obj = self.get_template(template_name, template_version)

        # 直接使用实例的 field_values
        standardized = copy.deepcopy(instance.field_values)

        # 应用模板规则（可选）
        if template_obj:
            for key, rule in template_obj.field_rules.items():
                if callable(rule):
                    standardized[key] = rule(standardized)
                elif isinstance(rule, str):
                    pass

        # 构造 SemanticObject
        semantic_obj = SemanticObject(
            agent_run_id=agent_run_id,
            object_name=instance.name,
            standardized_fields=standardized,
            schema_name=instance.schema_name,
            schema_version=instance.schema_version,
            template_name=template_obj.template_name if template_obj else None,
            template_version=template_obj.version_id if template_obj else None,
            timestamp=datetime.now()
        )

        # 录入数据库
        self._save_semantic_object_to_db(semantic_obj)

        return semantic_obj

    # -----------------------
    # 历史查询
    # -----------------------

    def query_historical_semantics(self,
                                    agentic_run_id: Optional[str] = None,
                                    object_name: Optional[str] = None,
                                    schema_name: Optional[str] = None,
                                    schema_version: Optional[str] = None,
                                    template_name: Optional[str] = None,
                                    template_version: Optional[str] = None
                                    ) -> List[SemanticObject]:
        """
        从数据库中检索符合要求的SemanticalObject并返回，可传入以下参数：
        - agentic_run_id: 可选，过滤特定 Agent 运行 ID
        - object_name: 可选，过滤特定对象名称
        - schema_name: 可选，过滤特定 Schema 名称
        - schema_version: 可选，过滤特定 Schema 版本，必须同时传入 schema_name
        - template_name: 可选，过滤特定 Template 名称
        - template_version: 可选，过滤特定 Template 版本，必须同时传入 template_name
        """
        session = get_session()
        try:
            query = session.query(SemanticObjectModel)

            # 按 agentic_run_id 过滤
            if agentic_run_id:
                query = query.filter(SemanticObjectModel.agent_run_id == agentic_run_id)

            # 按 object_name 过滤
            if object_name:
                query = query.filter(SemanticObjectModel.object_name == object_name)

            # 按 schema_name 过滤
            if schema_name:
                query = query.filter(SemanticObjectModel.schema_name == schema_name)

            # 按 schema_version 过滤（必须同时传入 schema_name）
            if schema_version and schema_name:
                query = query.filter(SemanticObjectModel.schema_version == schema_version)

            # 按 template_name 过滤
            if template_name:
                query = query.filter(SemanticObjectModel.template_name == template_name)

            # 按 template_version 过滤（必须同时传入 template_name）
            if template_version and template_name:
                query = query.filter(SemanticObjectModel.template_version == template_version)

            # 按创建时间降序排列
            query = query.order_by(SemanticObjectModel.created_at.desc())

            db_objects = query.all()

            # 转换为 SemanticObject Pydantic 模型
            return [
                SemanticObject(
                    agent_run_id=obj.agent_run_id,
                    object_name=obj.object_name,
                    standardized_fields=obj.standardized_fields,
                    schema_name=obj.schema_name,
                    schema_version=obj.schema_version,
                    template_name=obj.template_name,
                    template_version=obj.template_version,
                    timestamp=obj.timestamp
                )
                for obj in db_objects
            ]
        finally:
            session.close()

    # -----------------------
    # 变更审计
    # -----------------------

    def get_change_log(self,
                       object_name: Optional[str] = None,
                       limit: Optional[int] = None) -> List[ChangeRecord]:
        """
        从数据库获取变更日志

        Args:
            object_name: 可选，过滤特定对象名称
            limit: 可选，限制返回记录数量

        Returns:
            ChangeRecord 对象列表
        """
        session = get_session()
        try:
            query = session.query(ChangeRecordModel)

            if object_name:
                query = query.filter(ChangeRecordModel.object_name == object_name)

            # 按时间倒序排列
            query = query.order_by(ChangeRecordModel.timestamp.desc())

            if limit:
                query = query.limit(limit)

            db_records = query.all()

            return [
                ChangeRecord(
                    object_name=rec.object_name,
                    version_id=rec.version_id,
                    operator=rec.operator,
                    timestamp=rec.timestamp,
                    change_description=rec.change_description
                )
                for rec in db_records
            ]
        finally:
            session.close()

    # -----------------------
    # 便捷查询方法（未实现）
    # -----------------------
    # build_context 方法暂未实现，待 Context Engineering 阶段完善
