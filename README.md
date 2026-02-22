# 核价系统（Price Calculation System）

核价系统是一个用于管理项目成本计算的 Web 应用系统。  
当前版本不仅支持传统 Web 操作流程，同时正在演进为一个 **企业级 Agentic AI 成本管理系统**。

系统目标：

将大模型从“问答工具”升级为“可执行、可审计、可治理的企业级数字员工”。

---

# 快速开始

## 1️. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动应用

```bash
python run.py
```

**✨ 自动初始化**: 应用启动时会自动：
- 检查并创建数据库表（如果不存在）
- 检查并创建管理员用户（如果不存在）
  - 默认账号: `admin`
  - 默认密码: `admin123`
  - ⚠️ **请登录后立即修改密码！**

应用将在 `http://localhost:5000` 启动。


## Agentic System 架构（V1）
Agentic System 架构（V1）

本系统已从传统 Web 应用架构扩展为 Agentic System 架构。

Agent 不再直接访问数据库，而是通过严格受控的 Tool 接口执行操作。

### 架构总览
```bash
LLM Layer (Brain)
        ↓
Orchestration Layer (FSM + Think-Act-Observe)
        ↓
Semantic Guard (Tool Access Control)
        ↓
Python Executor (Safe Runtime)
        ↓
Tool Layer (Agentic APIs)
        ↓
Service Layer (Domain Logic)
        ↓
Database
```

### 1. LLM Layer（认知层）

负责理解用户意图

根据 FSM 当前状态生成 Tool 调用

不具备数据库访问权限

不具备执行权限

### 2.Orchestration Layer（中央神经系统）

位置：

app/agentic/orchestration/

职责：

管理 FSM 状态机

运行 Think → Act → Observe 循环

组装 Prompt

控制工具调用时机

记录 Trace

处理异常状态（WAIT_USER / ERR_ESCALATE）

### 3. FSM（任务状态机）

当前核价主流程：

FILES_COLLECTION
→ CREATE_PROJECT
→ PARSE_FILE
→ VALIDATE_FILE
→ HUMAN_CORRECTION_LOOP
→ GENERATE_COST_SUMMARY
→ GENERATE_COST_REPORT
→ DONE

FSM 的作用：

明确业务阶段

限制工具调用范围

防止模型越权

支持异常恢复

### 4. Tool Layer（受控因果接口）

Tool 是 LLM 与现实世界之间的唯一合法接口。

已实现核心工具：
```bash
Tool	作用	修改数据库	不可逆
parse_file	解析 Excel 生成 Items	✅	❌
validate_file	执行业务规则校验	✅	❌
generate_cost_summary	生成不可变成本快照	✅	✅
```
所有工具必须：

返回 ToolResult
结构化错误分类
声明 ToolRiskProfile
通过 Executor 执行

### 5. Python Executor（安全执行层）

位置：
app/agentic/execution/
职责：
检查 allowlist
调用 ToolSpec
强制返回 ToolResult
捕获异常
保证协议一致性
Executor 不参与业务逻辑。

### 6. ToolResult 协议

所有工具统一返回：

ToolResult(
    ok: bool,
    error_type: ErrorType,
    error_message: str,
    data: dict,
    explanation: str,
    side_effect: bool,
    irreversible: bool,
    audit_ref_id: str
)

该结构支持：

FSM 决策
LLM 推理
审计追踪
异常分流

### 7. ErrorType 分类体系

统一结构化错误：
INPUT_ERROR
SCHEMA_ERROR
BUSINESS_RULE_ERROR
VALIDATION_ERROR
PERMISSION_DENIED
DATABASE_ERROR
IRREVERSIBLE_CONFLICT
TOOL_NOT_ALLOWED
HUMAN_AUTH_REQUIRED
TIMEOUT_ERROR
SYSTEM_ERROR
避免字符串匹配式错误判断。

### 8. 审计与 Trace

系统支持：
Tool 调用记录
状态转移记录
异常捕获记录
不可逆操作记录

支持：
Agent 决策回放
异常复盘
企业合规治理

✅ 功能特性
Web 功能
✅ 自动初始化数据库
✅ 项目管理
✅ 文件上传
✅ Excel 自动解析
✅ 数据校验
✅ 成本计算
✅ 报告生成
✅ 审计日志
✅ 用户权限管理

Agentic 功能

✅ FSM 驱动业务流程
✅ Tool 执行层
✅ 风险建模
✅ 结构化错误体系
✅ 可扩展 Agent Runtime
🚧 HUMAN_CORRECTION_LOOP 正在增强
🚧 多 Agent 协作规划中

🏗 技术栈

后端: Flask 2.3.3
前端: Tailwind CSS + Alpine.js
数据库: SQLite (SQLAlchemy ORM)
Agent Runtime: 自研 Orchestration + Tool Framework
审计机制: AuditLogService
状态管理: FSM 驱动

📂 目录结构
```bash
price-caculation-system/
├── app/
│   ├── agentic/              # Agentic Runtime
│   │   ├── execution/        # Executor + ToolRegistry
│   │   ├── orchestration/    # FSM + Orchestrator
│   │   ├── schemas/          # DTO + ToolResult + ErrorType
│   │   └── tools/            # Agent Tools
│   ├── db/                   # 数据库
│   ├── models/               # ORM 模型
│   ├── services/             # 业务逻辑层
│   ├── routes/               # Web 路由
│   ├── logger.py/        
│   └── app_factory.py/   
├── build/    
├── docs/         
├── templates/
├── uploads/
├── flask_session/
├── run.py                    # app启动入口
├── start_app.py              # 用户端封装启动入口
└── requirements.txt
```

🔧 环境变量
可通过环境变量配置：
HOST
PORT
FLASK_DEBUG
SECRET_KEY
DATABASE_URL
MAX_UPLOAD_SIZE

🧪 故障排除
数据库错误
```bash
python app/db/auto_init.py
```
依赖问题
```bash
pip install -r requirements.txt
```
权限问题

确保以下目录有写入权限：

uploads/excel/
flask_session/

🎯 项目愿景

本系统正在演进为：
面向企业的可扩展 Agentic 成本管理系统
未来规划：
多任务 FSM 支持
多 Agent 协作
Tool Contract 版本治理
Prompt Policy 版本管理
Agent 生命周期管理
企业级权限与策略引擎

📌 相关文档
PRD: 核价系统PRD_core.docx
架构设计: ARCHITEXTURE_V0.1.docx
Agent 设计文档: Agent设计框架V1
UI 设计: price-side/UI_DESIGN.md
用户流程: price-side/USER_FLOW.md