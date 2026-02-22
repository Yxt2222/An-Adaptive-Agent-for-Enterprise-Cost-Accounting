# 前端功能实现状态

本文档总结了新增服务功能在前端页面的实现情况。

## 📊 功能实现状态总览

| 功能 | 后端服务 | 前端显示 | 前端交互 | 状态 |
|------|---------|---------|---------|------|
| confirmed 状态显示 | ✅ | ✅ | ❌ | 部分实现 |
| 确认警告项功能 | ✅ | ⚠️ | ❌ | 未实现 |
| 手动创建物流项 | ✅ | ❌ | ❌ | 未实现 |
| confirmed_count 统计 | ✅ | ✅ | - | 已实现 |

---

## 1. ✅ confirmed 状态显示（已实现）

### 后端支持
- `ValidationService` 支持 `confirmed` 状态
- `ValidationReport` 包含 `confirmed_count` 字段
- `ItemEditService.confirm_warning_item()` 方法可用

### 前端实现
**✅ 已实现** - 在 `templates/file/detail.html` 中：

1. **状态标签显示**：
```html
{% elif item.status.value == 'confirmed' %}bg-blue-100 text-blue-800
...
{% elif item.status.value == 'confirmed' %}已确认
```

2. **校验报告提示**：
```html
<p class="text-sm text-yellow-800">
    存在 {{ validation_report.warning_count }} 个警告项，可以人工确认后继续
</p>
```

3. **成本计算时包含 confirmed 项**：
```python
# app/routes/report.py
MaterialItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed])
PartItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed])
LaborItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed])
LogisticsItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed])
```

### 缺失功能
❌ **缺少确认按钮/操作**：
- 没有"确认"按钮来调用 `confirm_warning_item()`
- 没有路由来处理确认请求
- 用户无法通过界面确认警告项

---

## 2. ❌ 确认警告项功能（未实现）

### 后端支持
✅ `ItemEditService.confirm_warning_item()` 方法完整实现

### 前端实现
❌ **完全未实现**：
- 没有确认按钮
- 没有确认路由
- 没有确认表单或模态框

### 需要添加的功能

1. **路由** (`app/routes/file.py`):
```python
@file_bp.route('/<file_id>/items/<item_id>/confirm', methods=['POST'])
def confirm_item(project_id, file_id, item_id):
    """确认警告项"""
    # 调用 item_edit_service.confirm_warning_item()
```

2. **模板** (`templates/file/detail.html`):
```html
{% if item.status.value == 'warning' %}
<form method="POST" action="{{ url_for('file.confirm_item', ...) }}">
    <button type="submit" class="...">确认</button>
</form>
{% endif %}
```

---

## 3. ❌ 手动创建物流项功能（未实现）

### 后端支持
✅ `ExcelIngestService.parse_manual_logistics_item()` 方法完整实现

### 前端实现
❌ **完全未实现**：
- 没有手动创建物流项的页面
- 没有表单来输入物流项信息
- 没有路由来处理创建请求

### 需要添加的功能

1. **路由** (`app/routes/file.py` 或新建 `app/routes/logistics.py`):
```python
@file_bp.route('/manual-logistics', methods=['GET', 'POST'])
def create_manual_logistics(project_id):
    """手动创建物流项"""
    if request.method == 'POST':
        description = request.form.get('description')
        subtotal = request.form.get('subtotal')
        # 调用 excel_ingest_service.parse_manual_logistics_item()
```

2. **模板** (新建 `templates/logistics/create.html` 或在项目详情页添加):
```html
<form method="POST" action="{{ url_for('file.create_manual_logistics', project_id=project.id) }}">
    <input name="description" placeholder="备注描述">
    <input name="subtotal" type="number" placeholder="小计金额">
    <button type="submit">创建物流项</button>
</form>
```

3. **项目详情页添加入口** (`templates/project/detail.html`):
```html
<!-- 在物流成本表卡片中添加 -->
<a href="{{ url_for('file.create_manual_logistics', project_id=project.id) }}">
    手动添加物流项
</a>
```

---

## 4. ✅ confirmed_count 统计显示（已实现）

### 后端支持
✅ `ValidationReport.confirmed_count` 字段

### 前端实现
⚠️ **部分实现**：
- 模板中显示了 `warning_count` 和 `blocked_count`
- 但没有显示 `confirmed_count` 的统计卡片

### 建议改进

在 `templates/file/detail.html` 的校验结果概览中添加：

```html
<div class="grid grid-cols-5 gap-4 mb-4">  <!-- 改为 5 列 -->
    <!-- 现有统计... -->
    <div class="text-center p-4 bg-blue-50 rounded-lg">
        <div class="text-2xl font-bold text-blue-600">{{ validation_report.confirmed_count }}</div>
        <div class="text-sm text-gray-600">已确认</div>
    </div>
</div>
```

---

## 📝 总结

### 已实现的功能
1. ✅ `confirmed` 状态的显示（标签、颜色）
2. ✅ `confirmed` 项参与成本计算
3. ✅ 校验报告提示可以确认警告项

### 未实现的功能
1. ❌ **确认警告项的操作按钮和路由**
2. ❌ **手动创建物流项的页面和功能**
3. ❌ **confirmed_count 统计显示**

### 优先级建议

**高优先级**：
1. 添加确认警告项功能（用户需要能够确认数据项）
2. 添加 confirmed_count 统计显示（完善校验报告）

**中优先级**：
3. 添加手动创建物流项功能（根据实际需求）

---

## 🔧 快速修复建议

如果需要快速实现这些功能，可以参考 `price-side` 中的实现，或者我可以帮你添加这些功能的路由和模板。

