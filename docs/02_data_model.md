# 02 · 数据模型设计说明（V0.1）

本文档系统性说明 **产品成本统计系统 V0.1** 的数据模型设计。  
设计目标不是“字段齐全”，而是**保证核价结果可溯源、可校验、可审计、不可篡改**。

---

##一. Project（项目）

### 1. 实体说明

Project 表示一次 **产品成本核算的最小业务单元**。  
它不是合同本身，也不是单一产品型号，而是**围绕某一产品 / 项目进行的一次完整核价上下文**。

---

### 2. 字段定义

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | UUID / bigint (PK) | 系统唯一标识（system_id） |
| business_code | varchar | 产品编号（允许重复） |
| contract_code | varchar \| NULL | 项目 / 合同编号（可缺失） |
| raw_name | varchar | 原始产品名称（Excel 原样） |
| normalized_name | varchar \| NULL | 标准化产品名（人工确认） |
| spec_tags | json array | 产品特征标签，如 `["36m", "双逃生通道"]` |
| identifier_status | enum | 产品编号状态：`ok / duplicate / missing` |
| name_status | enum | 项目名处理状态：`raw / normalized / confirmed` |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

---

### 3. 字段可变性与来源规则（V0.1 核心约束）

| 字段 | 来源 | 修改规则 |
|---|---|---|
| id | 系统生成 | ❌ 不允许修改 |
| business_code | 解析 FileRecord 生成 | ✅ 允许修改，必须记录 AuditLog |
| contract_code | 解析 FileRecord 生成 | ✅ 允许修改，必须记录 AuditLog |
| raw_name | 解析 FileRecord 生成 | ❌ 只写一次，之后只读 |
| normalized_name | Name Mapping / 人工确认 | ✅ 允许修改，必须记录 AuditLog |
| spec_tags | 解析 FileRecord 生成 | ✅ 允许修改，必须记录 AuditLog |
| identifier_status | 系统规则计算 | ⚙️ 仅系统可修改 |
| name_status | 系统状态机 | ⚙️ 仅系统可修改 |
| created_at | 系统生成 | ❌ 不允许修改 |
| updated_at | 系统生成 | ⚙️ 仅系统可修改 |

---

### 4. 设计要点说明

- **raw_name 是事实字段**  
  - 来自 Excel 原始输入  
  - 一经写入即不可更改，用于审计与追溯  

- **normalized_name 是业务认知字段**  
  - 用于统一命名、后续统计与分析  
  - 必须支持人工修正，并完整记录修改历史  

- **identifier_status / name_status 是系统状态字段**  
  - 不接受人工直接写入  
  - 仅由校验逻辑与状态机驱动  

- **允许“纠错”，但不允许“无痕修改”**  
  - 所有可人工修改字段必须产生 `AuditLog`

---

> Project 的设计目标不是“字段完备”，  
> 而是 **保证一次核价中，产品身份的来源、修正与确认过程完全可追溯**。


## 二. FileRecord（原始文件记录）

### 1. 实体说明

FileRecord 表示 **一份被上传的原始成本来源文件（Excel）**，  
是系统中**所有成本计算结果的最小可追溯证据单元**。

核心职责：

- 区分文件类型（材料 / 配件 / 人工 / 物流等）
- 与 Project 建立强外键关系
- 作为 Item 明细与 CostSummary 的**唯一合法来源**
- 支持版本化，**不覆盖、不删除、只追加**

> 没有 FileRecord，就不允许存在任何可计算的成本数据。

---

### 2. 设计原则（V0.1 强约束）

- **同一类型文件可多次上传（版本化）**
- 每次上传：
  - 必须生成 **新的 FileRecord.id**
  - 即使文件内容完全相同，也不复用 id
- **禁止覆盖旧文件**
- **禁止删除历史文件**
- 成本计算逻辑 **只引用 `latest + valid` 的 FileRecord**
- 所有历史成本结果必须能完整回溯到当时使用的 FileRecord

---

### 3. 版本化上传规则

当用户对**同一类型表**执行“修改 / 重新上传”操作时：

- 新建一条 FileRecord
- `version = 上一版本 + 1`
- `storage_path` 指向新文件
- `file_hash` 重新计算
- 旧 FileRecord 保留，不做任何修改

---

### 4. 字段定义

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | PK | 系统自动生成的唯一标识（每次上传唯一） |
| project_id | FK → Project.id | 所属项目 |
| file_type | enum | `material_plan / part_plan / purchase_cost / labor_cost / logistics_cost` |
| original_name | varchar | 原始 Excel 文件名 |
| storage_path | varchar | 文件存储地址 |
| uploader_id | varchar | 上传人 ID |
| version | int | 文件版本号 |
| file_hash | varchar | 文件字节内容哈希（相同内容 → 相同 hash） |
| created_at | datetime | 上传时间 |
| updated_at | datetime | 修改时间 |
| parse_status | enum | 解析状态：`pending / parsed / failed` |
| validation_status | enum | 业务校验状态 |
| locked | bool | 是否已被 CostSummary 使用并冻结 |

---

### 5. 字段来源与可变性规则（非常重要）

| 字段 | 来源 | 修改规则 |
|---|---|---|
| id | 系统生成 | ❌ 不允许修改 |
| project_id | 上下文选择项目 | ❌ 不允许修改 |
| file_type | 上下文选择类型 | ❌ 不允许修改 |
| original_name | 上传 Excel 原始文件名 | ❌ 不允许修改 |
| uploader_id | 当前登录用户 | ❌ 不允许修改 |
| storage_path | 系统生成 | ❌ 不允许修改 |
| version | 系统版本控制 | ⚙️ 仅系统可修改 |
| file_hash | 系统计算 | ⚙️ 仅系统可修改 |
| created_at | 系统生成 | ❌ 不允许修改 |
| updated_at | 系统生成 | ⚙️ 仅系统可修改 |
| parse_status | 系统解析流程 | ⚙️ 仅系统可修改 |
| validation_status | 系统校验流程 | ⚙️ 仅系统可修改 |
| locked | CostSummary 生成逻辑 | ⚙️ 仅系统可修改 |

---

### 6. 状态字段说明

#### 6.1 parse_status（解析状态）

| 状态 | 含义 |
|---|---|
| pending | 文件已上传，尚未解析 |
| parsed | 解析成功，已生成 Item 明细 |
| failed | 解析失败，需要重新上传 |

#### 6.2 validation_status（业务校验状态）

> 由 Item 校验结果聚合得出，用于判断是否允许进入成本计算流程。

（具体状态枚举在 `Validation Rules` 文档中详细说明）

---

### 7. locked 字段说明

- `locked = true` 表示：
  - 该 FileRecord **已经参与过 CostSummary 生成**
  - 其对应的成本结果已经成为历史事实
- 被锁定的 FileRecord：
  - ❌ 不允许修改
  - ❌ 不允许作为“当前版本”再次参与计算
- 新的成本计算 **必须基于更新版本的 FileRecord**

---

### 8. 与成本明细的关系

- 每一个成功解析的 FileRecord：
  - 会生成 **对应类型的 Item 明细表**
  - 所有 Item 必须携带 `source_file_id`
- Item 的存在 **依赖 FileRecord**
- CostSummary 的合法性 **依赖其引用的 FileRecord 集合**

---

> FileRecord 的设计目标只有一个：  
> **保证任何一个成本数字，都能回答三个问题：**
>
> 1. 用的是哪一份文件？
> 2. 当时用的是第几版？
> 3. 文件是谁、在什么时候上传的？


## 三. MaterialItem（材料明细）

### 1. 实体说明

MaterialItem 表示 **已经完成标准化、可直接参与核价计算的材料明细行**。

设计要点：

- 与 Excel **完全解耦**，仅保留结构化、可计算字段
- 每一条 MaterialItem：
  - 必须能追溯到其来源 `FileRecord`
  - 必须明确是否参与成本计算
- 支持对 Excel 中给出的 `subtotal` 与 **理论计算值** 的一致性校验

---

### 2. 成本计算规则

理论计算公式：

```text
subtotal_theoretical = 0.001 × weight_kg × unit_price
```
### 3. 字段定义
| 字段名             | 类型                 | 说明                                   |
| --------------- | ------------------ | ------------------------------------ |
| id              | PK                 | 系统生成的唯一标识                            |
| project_id      | FK → Project.id    | 从属项目                                 |
| source_file_id  | FK → FileRecord.id | 来源文件                                 |
| raw_name        | varchar            | 原始材料名称                               |
| normalized_name | varchar | NULL     | 标准化材料名称                              |
| spec            | varchar            | 规格型号（区分同名不同尺寸/型号）                    |
| supplier        | varchar            | 供应商                                  |
| quantity        | decimal            | 数量                                   |
| unit            | varchar            | 单位                                   |
| material_grade  | varchar            | 材质                                   |
| weight_kg       | decimal | NULL     | 参考重量                                 |
| unit_price      | decimal            | 单价（每吨）                               |
| subtotal        | decimal            | 小计金额                                 |
| status          | enum               | `ok / warning / confirmed / blocked` |
| is_calculable   | bool               | 是否参与金额计算                             |
| created_at      | datetime           | 创建时间                                 |
| updated_at      | datetime           | 修改时间                                 |

### 4. 字段来源与可变性规则
| 字段              | 来源               | 修改规则                           |
| --------------- | ---------------- | ------------------------------ |
| id              | 系统生成             | ❌ 不允许修改                        |
| project_id      | 解析 FileRecord 生成 | ❌ 不允许修改                        |
| source_file_id  | 解析 FileRecord 生成 | ❌ 不允许修改                        |
| raw_name        | 解析 FileRecord 生成 | ❌ 不允许修改                        |
| normalized_name | Name Mapping 生成  | ✅ 允许修改（非空），需 AuditLog          |
| spec            | 解析 FileRecord 生成 | ✅ 允许修改，需 AuditLog              |
| supplier        | 解析 FileRecord 生成 | ✅ 允许修改，需 AuditLog              |
| quantity        | 解析 FileRecord 生成 | ✅ 允许修改，需 AuditLog，触发 status 计算 |
| unit            | 解析 FileRecord 生成 | ✅ 允许修改，需 AuditLog，触发 status 计算 |
| material_grade  | 解析 FileRecord 生成 | ✅ 允许修改，需 AuditLog              |
| weight_kg       | 解析 FileRecord 生成 | ✅ 允许修改，需 AuditLog，触发 status 计算 |
| unit_price      | 解析 FileRecord 生成 | ✅ 允许修改，需 AuditLog，触发 status 计算 |
| subtotal        | Excel / 系统计算     | ⚙️ 仅系统可修改                      |
| status          | 系统维护             | ⚙️ 用户不可直接修改                    |
| is_calculable   | 系统维护             | ⚙️ 用户不可修改                      |
| created_at      | 系统生成             | ❌ 不允许修改                        |
| updated_at      | 系统生成             | ⚙️ 仅系统可修改                      |


## 四. PartItem（配件明细）

### 说明

标准化配件明细，只存储已经标准化、可计算的数据。  
与 Excel 解耦，每条记录都能追溯其来源文件。

计算规则：

```text
Subtotal = quantity × unit_price
```

### 字段定义

| 字段名             | 类型                 | 说明                         |
| --------------- | ------------------ | -------------------------- |
| id              | PK                 | 系统生成的唯一标识                  |
| project_id      | FK → Project.id    | 从属项目                       |
| source_file_id  | FK → FileRecord.id | 来源文件                       |
| raw_name        | varchar            | 原始配件名称                     |
| normalized_name | varchar | NULL     | 标准化配件名称                    |
| supplier        | varchar            | 供应商                        |
| spec            | varchar            | 规格型号，用于区分同名但不同尺寸 / 型号的配件   |
| quantity        | decimal            | 数量                         |
| unit            | varchar            | 单位                         |
| unit_price      | decimal            | 单价                         |
| bundle_key      | varchar            | 组合键（非空），同一次采购的配件组合键一致      |
| subtotal        | decimal            | 小计                         |
| status          | enum               | `ok / warning / confirmed` |
| is_calculate    | bool               | 是否纳入数值计算（是否锚点行）            |
| create_at       | datetime           | 创建时间                       |
| update_at       | datetime           | 修改时间                       |



### 字段来源与可变性规则

| 字段              | 来源                      | 修改规则                             |
| --------------- | ----------------------- | -------------------------------- |
| id              | 系统生成                    | ❌ 不允许修改                          |
| project_id      | 解析 FileRecord 生成        | ❌ 不允许修改                          |
| source_file_id  | 解析 FileRecord 生成        | ❌ 不允许修改                          |
| raw_name        | 解析 FileRecord 生成        | ❌ 不允许修改                          |
| normalized_name | Map 生成                  | ✅ 允许人工修改（非空），需 AuditLog          |
| spec            | 解析 FileRecord 生成        | ✅ 允许人工修改，需 AuditLog              |
| supplier        | 解析 FileRecord 生成        | ✅ 允许人工修改，需 AuditLog              |
| quantity        | 解析 FileRecord 生成        | ✅ 允许人工修改，需 AuditLog，触发 status 计算 |
| unit            | 解析 FileRecord 生成        | ✅ 允许人工修改，需 AuditLog，触发 status 计算 |
| unit_price      | 解析 FileRecord 生成        | ✅ 允许人工修改，需 AuditLog，触发 status 计算 |
| bundle_key      | 系统生成                    | ❌ 不允许修改                          |
| subtotal        | 解析 FileRecord 生成 / 系统计算 | ⚙️ 仅系统可修改                        |
| status          | 系统维护                    | ⚙️ 用户不可直接修改                      |
| is_calculate    | 系统生成                    | ⚙️ 用户不可修改                        |
| create_at       | 系统生成                    | ❌ 不允许修改                          |
| update_at       | 系统生成                    | ❌ 不允许修改                          |



## 五. LaborItem（加工费明细）

### 说明

标准化加工费明细，只存储已经标准化、可计算的数据。  
与 Excel 解耦，每条记录都能追溯来源文件。

计算规则：

```text
Processing_fee = work_quantity × unit_price
Subtotal = Processing_fee + Extra_subsidies + Ton_bonus
```

### 字段定义

| 字段名              | 类型                 | 说明                         |
| ---------------- | ------------------ | -------------------------- |
| id               | PK                 | 系统生成的唯一标识                  |
| project_id       | FK → Project.id    | 从属项目                       |
| source_file_id   | FK → FileRecord.id | 来源文件                       |
| raw_group        | varchar            | 初始读取的班组                    |
| normalized_group | varchar            | 标准映射后的班组                   |
| work_quantity    | decimal            | 加工数量                       |
| unit             | varchar            | 单位                         |
| unit_price       | decimal            | 单价                         |
| extra_subsidies  | decimal            | 杂项补助（箱梁攻丝费、行走、液压站组装费、溜槽）   |
| ton_bonus        | decimal            | 吨位补助                       |
| subtotal         | decimal            | 小计                         |
| status           | enum               | `ok / warning / confirmed` |
| is_calculate     | bool               | 是否纳入数值计算（是否锚点行）            |
| create_at        | datetime           | 创建时间                       |
| update_at        | datetime           | 修改时间                       |



### 字段来源与可变性规则

| 字段               | 来源               | 修改规则                             |
| ---------------- | ---------------- | -------------------------------- |
| id               | 系统生成             | ❌ 不允许修改                          |
| project_id       | 解析 FileRecord 生成 | ❌ 不允许修改                          |
| source_file_id   | 解析 FileRecord 生成 | ❌ 不允许修改                          |
| raw_group        | 解析 FileRecord 生成 | ❌ 不允许修改                          |
| normalized_group | 解析 FileRecord 生成 | ✅ 允许人工修正，需 AuditLog              |
| work_quantity    | 解析 FileRecord 生成 | ✅ 允许人工修改，需 AuditLog，触发 status 计算 |
| unit             | 解析 FileRecord 生成 | ✅ 允许人工修改，需 AuditLog，触发 status 计算 |
| unit_price       | 解析 FileRecord 生成 | ✅ 允许人工修改，需 AuditLog，触发 status 计算 |
| extra_subsidies  | 解析 FileRecord 生成 | ✅ 允许人工修改，需 AuditLog，触发 status 计算 |
| ton_bonus        | 解析 FileRecord 生成 | ✅ 允许人工修改，需 AuditLog，触发 status 计算 |
| subtotal         | 系统统一计算           | ⚙️ 仅系统可修改                        |
| status           | 系统维护             | ⚙️ 用户不可直接修改                      |
| is_calculate     | 系统生成             | ⚙️ 用户不可修改                        |
| create_at        | 系统生成             | ❌ 不允许修改                          |
| update_at        | 系统生成             | ❌ 不允许修改                          |


## 六. LogisticsItem

### 说明

标准化运费明细。  
V0.1 支持 LogisticsItem 不通过上传 File，而是通过输入创建。

---

### 字段定义

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | PK | 系统生成的唯一标识 |
| project_id | FK → Project.id | 从属项目 |
| source_file_id | FK → FileRecord.id | 来源文件 |
| type | enum | `[transport / install]` |
| description | varchar | 描述，空为 NULL |
| subtotal | decimal | 总价格 |
| status | enum | `ok / warning / confirmed` |
| is_calculate | bool | 是否纳入数值计算（是否锚点行） |
| create_at | datetime | 创建时间 |
| update_at | datetime | 修改时间 |

---

### 字段来源与可变性规则

| 字段 | 来源 | 修改规则 |
|---|---|---|
| id | 系统生成 | ❌ 不允许修改 |
| project_id | 解析 FileRecord 生成 | ❌ 不允许修改 |
| source_file_id | 解析 FileRecord 生成 | ❌ 不允许修改 |
| type | 解析 FileRecord 生成 | ❌ 不允许修改 |
| description | 解析 FileRecord 生成 | ✅ 允许人工修改，需 AuditLog |
| subtotal | 解析 FileRecord 生成 | ✅ 允许人工修改，需 AuditLog，触发 status 计算（V0.1 默认人工输入可用） |
| status | 系统维护 | ⚙️ 用户不可直接修改 |
| is_calculate | 系统生成 | ⚙️ 用户不可修改 |
| create_at | 系统生成 | ❌ 不允许修改 |
| update_at | 系统生成 | ❌ 不允许修改 |


## 七.CostSummary

CostSummary 一经生成，不会因底层 FileRecord 或 Item 变更而自动更新；  
如需重新核价，系统将生成新的 CostSummary 记录。

---

### 字段定义

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | PK | 系统生成的唯一标识 |
| project_id | PK | 从属项目 |
| material_cost | decimal | 材料总价格 |
| part_cost | decimal | 配件总价格 |
| labor_cost | decimal | 劳动加工总费用 |
| logistics_cost | decimal | 物流或安装总费用 |
| total_cost | decimal | 全部总价格 |
| material_file_id | varchar | 计算所基于的 material_file_id |
| part_file_id | varchar | 计算所基于的 part_file_id |
| labor_file_id | varchar | 计算所基于的 labor_file_id |
| logistics_file_id | varchar | 计算所基于的 logistics_file_id |
| calculated_at | datetime | 统计时间 |
| calculation_version | varchar | 核价规则版本 |
| status | enum | `[active / replaced]` |
| invalidated_at | datetime | 被弃用时间 |
| replaces_cost_summary_id | varchar | 替代的 CostSummary ID |

---

### 字段来源与可变性规则

| 字段 | 来源 | 修改规则 |
|---|---|---|
| id | 系统生成 | ❌ 不允许修改 |
| project_id | 核价上下文确定 | ❌ 不允许修改 |
| material_cost | 系统根据 material_file 计算 | ⚙️ 仅系统可修改 |
| part_cost | 系统根据 part_file 计算 | ⚙️ 仅系统可修改 |
| labor_cost | 系统根据 labor_file 计算 | ⚙️ 仅系统可修改 |
| logistics_cost | 系统根据 logistics_file 计算 | ⚙️ 仅系统可修改 |
| material_file_id | 核价上下文确定 | ❌ 不允许修改 |
| part_file_id | 核价上下文确定 | ❌ 不允许修改 |
| labor_file_id | 核价上下文确定 | ❌ 不允许修改 |
| logistics_file_id | 核价上下文确定 | ❌ 不允许修改 |
| total_cost | 系统计算生成 | ❌ 不允许修改 |
| calculated_at | 系统生成 | ❌ 不允许修改 |
| calculation_version | 系统生成 | ❌ 不允许修改 |
| status | 系统初始化 | ✅ 允许人工根据业务修改 |
| invalidated_at | 系统生成 | ❌ 不允许修改 |
| replaces_cost_summary_id | 系统生成 | ❌ 不允许修改 |

## 八. AuditLog

工业级日志：使系统具备审计能力、责任追溯能力、决策可解释性。

---

### 字段定义

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | PK | 系统生成的唯一标识 |
| project_id | FK → Project.id | 从属项目 |
| entity_type | enum | `project / file / material / part / labor / logistic` |
| entity_id | bigint / UUID | 被修改实体的唯一识别 ID |
| action | enum | `confirm / modify / map（原始映射到标准） / override` |
| changed_attribute | enum | 指定实体属性列表中的字段 |
| before_value | json | 修改前的值 |
| after_value | json | 修改后的值 |
| operator_id | FK → User.id | 执行操作的用户 |
| timestamp | datetime | 修改时间 |

---

### 字段来源与不可变性规则

| 字段 | 来源 | 修改规则 |
|---|---|---|
| id | 系统生成 | ❌ 不允许修改 |
| project_id | 由被操作实体所属项目确定（可为空） | ❌ 不允许修改 |
| entity_type | 由被操作实体指向的类型确定 | ❌ 不允许修改 |
| entity_id | 由被操作实体指向的 ID 确定 | ❌ 不允许修改 |
| action | 系统根据触发行为确定 | ❌ 不允许修改 |
| changed_attribute | 由最终生效的变更字段确定 | ❌ 不允许修改 |
| before_value | 系统在变更前自动采集（不记录中间字段） | ❌ 不允许修改 |
| after_value | 系统在变更后自动采集（不记录中间字段） | ❌ 不允许修改 |
| operator_id | 系统根据操作上下文填充（用户 / system） | ❌ 不允许修改 |
| timestamp | 系统生成 | ❌ 不允许修改 |

## 九. User

系统操作者（Actor），不是员工档案。  
因此 User 模型应满足：登录稳定、审计可追责、信息最小化、不引入 HR 语义。

---

### 字段定义

| 字段名 | 类型 | 说明 |
|---|---|---|
| id | varchar (PK) | 系统生成的唯一标识 |
| account | varchar (unique, immutable) | 登录账号 |
| display_name | varchar | 显示名 |
| password_hash | varchar | 密码哈希 |
| email | varchar | 邮箱 |
| email_verified | bool | 邮箱验证状态 |
| phone_number | varchar | 手机号 |
| phone_verified | bool | 手机号验证状态 |
| is_active | bool | 账号是否可用 |
| created_at | datetime | 创建时间 |

---

### 字段来源与可变性规则

| 字段 | 来源 | 修改规则 |
|---|---|---|
| id | 系统生成 | ❌ 不允许修改 |
| account | 账号初始化生成 | ❌ 唯一登录标识，不可修改 |
| display_name | 账号初始化录入 | ✅ 员工可自行修改 |
| password_hash | 账号初始化创建 | ⚠️ 可重置覆盖，不允许读取 |
| phone_number | 账号初始化录入 | ✅ 员工可自行修改，需验证 |
| phone_verified | 系统生成 | ⚙️ 默认 `false`，验证后系统修改 |
| email | 账号初始化录入 | ✅ 员工可自行修改，需验证 |
| email_verified | 系统生成 | ⚙️ 默认 `false`，验证后系统修改 |
| is_active | 系统生成 | ⚙️ 创建时 `true`，注销时改为 `false` |
| created_at | 系统生成 | ❌ 不允许修改 |


## 九. NameMapping 

名字映射类
同一 raw_name 只能由一个 active 映射，历史映射通过 is_active = False 留下来

### 字段定义

| 字段名           | 类型/说明                              |
|------------------|---------------------------------------|
| id               | PK                                    |
| domain           | enum # PROJECT / MATERIAL / PART / LABOR_GROUP |
| raw_name         | varchar # 映射原始名                  |
| normalized_name  | varchar # 规范化名字                  |
| is_active        | Boolean # 是否启用                    |
| created_by       | user_id # 创建者                      |
| created_at       | datetime # 创见时间                   |
| updated_at       | datetime # 更新时间                   |

### 字段来源与可变性规则
| 字段名           |  来源     | 修改规则 |
|------------------|----------|----------|
| Id               | 系统生成|不允许修改 |
| domain           | 初始化时生成|不允许修改 |
| raw_name         | mapping 初始化时录入|不允许修改 |
| normalized_name  | mapping 初始化时录入|不允许修改 |
| is_active        | mapping 初始化时默认 True|允许人工触发系统修改 |
| created_by       | 系统生成|不允许修改 |
| created_at       | 系统生成|不允许修改 |
| updated_at       | 系统生成|不允许修改 |
