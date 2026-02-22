# 架构设计与理念（V0.1）
# 01_architecture.md — 系统架构说明（V0.1）

> 目标：把“产品直接生产成本核算”变成**可溯源、可校验、可审计、可复现、可冻结**的业务事实快照（CostSummary）。  
> V0.1 核心原则：**校验不等于修复；人工确认必须显式；证据不可被污染。** fileciteturn9file0

---

## 1. 分层架构（V0.1）

### 1.1 Layer 0：存储与持久化
- **DB（SQLAlchemy 2.0）**：存储 Project / FileRecord / Items / CostSummary / AuditLog / NameMapping / User 等结构化数据。
- **File Storage（本地路径）**：Excel 原始文件仅作为证据保留，系统通过 `FileRecord.storage_path` 指向文件。fileciteturn9file12

### 1.2 Layer 1：Domain Models（不可逆约束落地处）
- **Project**：业务对象（产品/合同维度），承载业务标识（business_code / contract_code）与规范名（normalized_name）。
- **FileRecord**：证据对象（文件版本化 + 状态机 + 锁定），是 Item 的唯一来源。
- **Cost Items**：MaterialItem / PartItem / LaborItem / LogisticsItem（均继承 BaseCostItemMixin）。
- **CostSummary**：核价快照（不可变），引用四类 FileRecord 版本并产出汇总值。
- **AuditLog**：不可变审计日志（create/update/system_update 等），覆盖上传、校验状态跃迁、人工修正等关键行为。fileciteturn9file0
- **NameMapping**：raw_name → normalized_name 映射库，用于项目名/材料名/配件名/班组名标准化。

### 1.3 Layer 2：Services（业务规则与事务边界）
V0.1 主要服务：
- AuditLogService
- NameNormalizationService
- UserService
- ProjectService
- FileRecordService
- ExcelIngestService（Parse）
- ValidationService（Validate）
- ItemEditService（人工修正/确认）
- CostCalculationService（生成快照 + 冻结 + 报告）

---

## 2. 关键实体与关系

### 2.1 关系图（文字版）

- `Project (1) —— (N) FileRecord`
- `FileRecord (1) —— (N) Item`（按 file_type 映射到不同 Item 表）
- `Project (1) —— (N) CostSummary`
- `CostSummary (1) —— (4) FileRecord`（material/part/labor/logistics，且记录各自 file_id）
- `AuditLog` 记录对 Project / FileRecord / Item / CostSummary 的关键变更（永不 update/delete）。

---

## 3. 核心主链路（端到端）

> 你在测试里跑通的主业务：用户 → 项目 → 上传 → parse → validate → 修正/确认 → 生成快照 → 导出报告。

### 3.1 用户与操作者（operator_id）
系统所有关键行为都必须带 `operator_id`：
- 上传文件（FileRecord.uploader_id）
- 修改 item（ItemEditService）
- 生成快照（CostCalculationService）
- 生成 DF 报告（报告“统计人”）

### 3.2 文件证据链（FileRecord）
FileRecord 的职责是“证据不可污染”：
- 版本化：同 project_id + file_type 下新增上传会生成新版本。
- 状态机：
  - `parse_status: pending → parsed/failed`
  - `validation_status: pending → ok/warning/confirmed/blocked`
- 锁定：当 CostSummary 引用时 `locked = True`，禁止继续通过 ItemEdit 修改。

### 3.3 Parse：ExcelIngestService
- 输入：`FileRecord`（含 storage_path 与 file_type）
- 输出：Items 批量入库 + FileRecord.parse_status 更新
- 特例：
  - `material_plan / part_plan`：只做可读性检查，不生成 items（parsed/failed）。
- 标准化：解析每行时调用 `NameNormalizationService.normalize()`，生成 normalized_name / normalized_group。fileciteturn9file12
- Part bundle 识别：通过“单价列是否被合并”推导 `bundle_key`，用于后续 bundle-aware 校验。

### 3.4 Validate：ValidationService
ValidationService 只做三件事：
1) 判定 Item 是否可信（status + error_codes + messages）
2) 聚合 FileRecord.validation_status
3) 返回可操作的问题清单（blocked_items / warning_items / report）

#### 3.4.1 Item status 语义（V0.1）
- `ok`：完整性 + 非负性 + 规则一致（数量关系）均通过
- `warning`：可参与核价但必须人工确认（例如仅人工兜底）
- `confirmed`：人工确认后的 warning（只能由 ItemEditService 触发）
- `blocked`：严重错误，禁止参与核价

#### 3.4.2 PartItem 的 bundle-aware 校验（核心差异点）
- 按 `bundle_key` 分组，`None` 或单行走普通校验。
- 多行 bundle：选择“锚点行（anchor）”并约束非锚点行的 subtotal：
  - 锚点优先级：system+manual > system-only > manual-only
  - 非锚点若 subtotal != 0 → **V0.1 直接阻断：blocked + BUNDLE_MULTI_ANCHOR**
  - 非锚点 `is_calculable=False`，避免被聚合入成本。


### 3.5 人工修正：ItemEditService
- 强约束：若 `FileRecord.locked=True` → 禁止修改（防证据污染）。
- 字段白名单：不同 item_type 可编辑字段不同，并区分“触发重校验字段”。
- 每次修改必须写 AuditLog（before/after）
- 若修改了数值字段：触发 `ValidationService.validate_file(file_record)` 只重校验所属文件。

### 3.6 生成快照：CostCalculationService（事务核心）
- 输入：project_id + 4 个 file_id + operator_id
- 预检查：
  - parse_status == parsed
  - validation_status in {ok, confirmed}
  - locked == false
- 计算：
  - 对每类 items 做 `sum(subtotal)`，并只纳入 `is_calculable=True` 的行（bundle 只算锚点）。
- 落库：
  - 新增 CostSummary（calculation_version 递增，status=active）
  - 作废旧 active summary（invalidated_at + replaces_cost_summary_id）
  - 锁定四个 FileRecord（locked=True）
  - 关键动作写 AuditLog（create + system）。fileciteturn9file15

### 3.7 导出报告：DataFrame Report
- 输入：active 的 CostSummary + operator_id
- 双重保险：再次检查引用文件 validation_status ∈ {ok, confirmed}
- 组装：
  - 项目信息（business_code / normalized_name / spec_tags / contract_code）
  - 四类 items 明细 + 小计合计 + “表上传人/表名/修改时间/版本”
  - 置信级别：ok→系统确认；confirmed→人工确认
- 输出：DataFrame（由上层决定是否写 Excel / 返回下载链接）。fileciteturn9file14

---

## 4. 关键机制与设计取舍

### 4.1 “证据不可污染”如何落地？
- FileRecord 版本化 + CostSummary 冻结引用 + FileRecord.locked 只升不降。
- 人工修正只允许发生在 locked=false 的 FileRecord 下。
- AuditLog 永不 update/delete，形成可追溯审计链。
- 生成快照的 filerecord 永远存储，永远不会被修改。
- item具有业务解释的功能，永远存储，生成快照后也永不会被修改。

### 4.2 “校验不等于修复”
ValidationService 不做自动修复（尤其是金额分摊/小计修正），只输出：
- status
- error_codes
- messages

修复只能通过 ItemEditService（人）或未来的“可解释修复策略”扩展。

### 4.3 bundle 为什么要引入 is_calculable？
- bundle 场景下 Excel 可能出现“合并单价、一次付款、多行记录”的结构。
- V0.1 不做自动分摊：因此只把锚点行纳入求和（is_calculable=True），其余行不计入成本但仍保留证据与明细。

### 4.4 Manual Logistics（人工运费/安装费）
V0.1 允许无需 Excel 录入物流费用：
- 创建一个 `file_type=manual` 的“伪 FileRecord”
- 直接创建 LogisticsItem（type/description/subtotal）
- validation 只做完整性（subtotal 非空）+ 非负性（>=0）
- 参与 CostSummary 汇总与报告导出（与普通物流文件一致）fileciteturn9file9

---

## 5. 可扩展点（V0.2+）

- **bundle 分摊策略**：引入 allocation 表或分摊规则引擎，而不是把分摊塞进 PartItem。
- **单位体系**：单位归一（吨/kg、元/万元）与阈值策略统一配置。
- **RBAC 与审批**：warning→confirmed 可引入“二次确认/审批流”。
- **报表模板**：支持多模板、多语言、多维统计（占比、环比、同类对比）。
- **外部系统对接**：ERP/PLM/财务软件接口（V0.1 明确不做）。fileciteturn9file4
