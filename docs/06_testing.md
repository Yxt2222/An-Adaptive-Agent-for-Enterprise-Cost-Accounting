# 06 · 测试和验证V0.1）

本文档记录 **产品成本统计系统 V0.1** 已完成的关键测试用例，覆盖主业务链路、核心不可逆约束以及高风险边界条件。  
所有测试均以**真实业务行为 + 实际 Service 调用**为基础完成。

---

## 1. 业务主线测试（已测）

**测试目标：**  
验证系统从“真实用户操作”到“最终成本报告”的完整闭环是否稳定、可复现。

### 测试流程
1. 创建用户
2. 创建项目
3. 上传 Excel 文件
4. 解析 Excel（Parse）
5. 校验数据（Validate）
6. 人工修正异常 Item
7. 生成 CostSummary
8. 生成并下载成本报告
9. 检验报告数据正确性与来源一致性

### 预期结果
- 全流程可顺利执行
- CostSummary 正确生成
- 报告内容与 Item / FileRecord / Project 信息一致
- 无隐式数据修改或证据污染

---

## 2. FileRecord 被锁定后再修改 Item（已测）

**测试目标：**  
验证 CostSummary 生成后，证据链不可被破坏。

### 测试行为
- 先生成 CostSummary（文件被锁定）
- 再调用 `ItemEditService` 修改 Item

### 预期结果
- ❌ 抛出异常
- ❌ 不允许修改 Item
- ❌ 不写入 AuditLog

👉 **这是系统“快照不可逆”的生命线测试**

---

## 3. validation_status = blocked 的 File 参与 CostSummary（已测）

**测试目标：**  
确保不可信数据无法进入成本快照。

### 测试行为
- FileRecord.validation_status = `blocked`
- 调用 `CostCalculationService`

### 预期结果
- ❌ 明确拒绝生成 CostSummary
- ❌ 不产生任何成本快照记录

---

## 4. PartItem Bundle 多锚点错误（已测）

**测试目标：**  
验证 Bundle 场景下复杂校验逻辑的正确性。

### 测试条件
- 同一 PartItem bundle 内
- 存在 **两行 subtotal ≠ 0**

### 预期结果
- 非锚点行 → `blocked`
- FileRecord.validation_status → `blocked`
- 明确返回 bundle 错误信息

---

## 5. 人工 Logistics 金额异常（已测）

**测试目标：**  
验证人工录入路径的安全性。

### 测试行为
- 人工创建 LogisticsItem
- `amount <= 0` 或为空

### 预期结果
- Item.status = `blocked`
- FileRecord.validation_status = `blocked`
- 无法参与 CostSummary

---

## 6. 重复生成 CostSummary（已测）

**测试目标：**  
验证成本快照的替代与版本管理逻辑。

### 测试行为
- 对同一组 FileRecord 再次生成 CostSummary

### 预期结果
- 旧 CostSummary → `replaced`
- 新 CostSummary → `active`
- 被引用的 FileRecord 仍保持 `locked = true`

---

## 7. 测试总结

V0.1 已覆盖以下关键风险点：

- ✅ 主业务闭环可用
- ✅ 快照不可逆约束有效
- ✅ 校验失败文件无法参与核价
- ✅ Bundle 复杂规则正确生效
- ✅ 人工输入路径安全
- ✅ 成本快照可版本替代、不可篡改

> **测试结论：V0.1 在“可信核价”这一核心目标上是稳定且可靠的。**

---
