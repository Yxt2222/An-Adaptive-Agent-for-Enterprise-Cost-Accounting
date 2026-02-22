# price-caculation-system vs price-side 主要差异

本文档总结了 `price-caculation-system`（新版本）与 `price-side`（旧版本）在 Models 和 Services 方面的主要变动。

## 📋 目录

- [Models 差异](#models-差异)
- [Services 差异](#services-差异)
- [总结](#总结)

---

## Models 差异

### 1. 文件名规范

| 文件 | price-side | price-caculation-system | 说明 |
|------|-----------|------------------------|------|
| 配件项模型 | `Part_item.py` | `part_item.py` | ✅ **已修正**: 统一使用小写命名规范 |

### 2. 模型定义

经过对比，**所有模型的定义基本一致**，包括：
- `User` - 用户模型
- `Project` - 项目模型
- `FileRecord` - 文件记录模型
- `MaterialItem` - 材料成本项模型
- `PartItem` - 配件成本项模型
- `LaborItem` - 人工成本项模型
- `LogisticsItem` - 物流成本项模型
- `CostSummary` - 成本汇总模型
- `AuditLog` - 审计日志模型
- `NameMapping` - 名称映射模型
- `BaseCostItemMixin` - 基础成本项混入类

**结论**: Models 层面没有功能性的变更，主要是文件命名规范的统一。

---

## Services 差异

### 1. ExcelIngestService（Excel 解析服务）

#### 🔴 关键差异：依赖注入

**price-caculation-system (新版本)**:
```python
def __init__(
    self,
    db: Session,
    audit_log_service: AuditLogService,
    name_normalization_service: NameNormalizationService,
    file_service: FileRecordService,  # ✅ 新增依赖
):
    self.db = db
    self.audit_log_service = audit_log_service
    self.name_normalization_service = name_normalization_service
    self.file_service = file_service  # ✅ 新增
```

**price-side (旧版本)**:
```python
def __init__(
    self,
    db: Session,
    audit_log_service: AuditLogService,
    name_normalization_service: NameNormalizationService,
    # ❌ 没有 file_service 依赖
):
    self.db = db
    self.audit_log_service = audit_log_service
    self.name_normalization_service = name_normalization_service
```

#### ✅ 新增功能：手动物流项解析

**price-caculation-system (新版本)** 新增了 `parse_manual_logistics_item()` 方法：

```python
def parse_manual_logistics_item(
    self,
    project_id: str,
    description: str,
    subtotal: float,
    operator_id: str
) -> tuple[FileRecord, LogisticsItem]:
    """
    用户手动添加 LogisticsItem 记录
    规则：用户输入相关数据 -> 生成 manual FileRecord -> 生成 LogisticsItem 记录 -> 入库
    """
    logistics_file = self.file_service.create_update_file_record(
        project_id=project_id,
        file_type=FileType.manual,
        operator_id=operator_id
    )
    logistics_item = LogisticsItem(
        id=str(uuid4()),
        project_id=project_id,
        source_file_id=logistics_file.id,
        type=LogisticsType.TRANSPORT,
        description=description,
        subtotal=subtotal,
    )
    self.db.add(logistics_item)
    self.db.commit()
    
    return logistics_file, logistics_item
```

**price-side (旧版本)**: 没有此方法

#### 🔧 物流类型处理差异

**price-caculation-system (新版本)**:
```python
# 直接使用 row.get("类型")
logistics_type=row.get("类型"),
```

**price-side (旧版本)**:
```python
# 解析类型字段，转换为 LogisticsType 枚举
type_str = str(row.get("类型", "")).strip().lower()
logistics_type = LogisticsType.OTHER
if "运输" in type_str or "transport" in type_str:
    logistics_type = LogisticsType.TRANSPORT
elif "安装" in type_str or "installation" in type_str:
    logistics_type = LogisticsType.INSTALLATION

# 使用解析后的枚举
type=logistics_type,
```

---

### 2. ValidationService（数据校验服务）

#### ✅ 新增功能：confirmed 状态支持

**price-caculation-system (新版本)** 新增了 `confirmed` 状态的支持：

1. **ValidationReport 新增字段**:
```python
@dataclass
class ValidationReport:
    total_items: int
    ok_count: int
    warning_count: int
    confirmed_count: int  # ✅ 新增
    blocked_count: int
    # ...
```

2. **校验逻辑支持 confirmed 状态**:
```python
# 在 _validate_material_item, _validate_part_item, 
# _validate_labor_item, _validate_logistics_item 中
if item.status == CostItemStatus.confirmed:
    return ItemValidationResult(
        item_id=item.id,
        status="confirmed",
        messages=["Item manually confirmed by user"],
    )
```

3. **状态聚合支持 confirmed**:
```python
# 在 _aggregate_file_status 中
if "confirmed" in statuses:
    return ValidationStatus.confirmed
```

**price-side (旧版本)**: 没有 `confirmed_count` 字段和相关的 `confirmed` 状态处理逻辑

#### 🔧 人工成本项校验差异

**price-side (旧版本)** 有额外的校验逻辑：
```python
# manual-only → warning
if anchor_result.status == "ok":
    has_system = anchor.quantity is not None and anchor.unit_price is not None
    if not has_system:
        # 处理逻辑...
```

**price-caculation-system (新版本)**: 没有此额外校验逻辑

---

## 总结

### 主要变动

1. **✅ 文件命名规范**: `Part_item.py` → `part_item.py`

2. **✅ ExcelIngestService 增强**:
   - 新增 `FileRecordService` 依赖注入
   - 新增 `parse_manual_logistics_item()` 方法，支持手动创建物流项
   - 物流类型处理方式不同（新版本更简单直接）

3. **✅ ValidationService 增强**:
   - 新增 `confirmed` 状态支持
   - 新增 `confirmed_count` 统计
   - 支持用户手动确认的数据项

### 影响

1. **服务初始化顺序变化**:
   - 新版本中 `ExcelIngestService` 需要 `FileRecordService` 作为依赖
   - 初始化顺序：`FileRecordService` → `ExcelIngestService`

2. **功能增强**:
   - 支持手动创建物流成本项
   - 支持用户确认数据项（confirmed 状态）
   - 更完善的校验报告统计

3. **向后兼容性**:
   - Models 层面完全兼容
   - Services 层面需要更新初始化代码（已在 `test.ipynb` 中体现）

### 建议

在使用 `price-caculation-system` 时：
1. ✅ 使用新的服务初始化顺序（参考 `draft/test.ipynb`）
2. ✅ 注意 `ExcelIngestService` 需要 `file_service` 参数
3. ✅ 利用新的 `confirmed` 状态功能来标记用户已确认的数据项
4. ✅ 使用 `parse_manual_logistics_item()` 方法手动创建物流项

