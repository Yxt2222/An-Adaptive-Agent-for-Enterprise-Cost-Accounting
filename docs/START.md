# 核价系统 Web 界面启动指南

## 快速开始

### 1. 安装依赖

```bash
cd price-caculation-system
pip install -r requirements.txt
```

### 2. 启动应用（自动初始化）

```bash
cd price-caculation-system
python run.py
```

**✨ 新功能**: 应用启动时会自动检查并执行初始化：
- 如果数据库表不存在，会自动创建
- 如果管理员用户不存在，会自动创建（账号: `admin`, 密码: `admin123`）

应用将在 `http://localhost:5000` 启动。

### 手动初始化（可选）

如果需要手动初始化，也可以使用：

```bash
# 初始化数据库表
cd price-caculation-system
python -c "from app.db.init_db import init_db; init_db(); print('✅ Database tables created')"

# 创建管理员用户
cd price-caculation-system
python create_admin.py
```

或者使用自动初始化脚本：

```bash
cd price-caculation-system
python app/db/auto_init.py
```

## 功能说明

### 已实现的功能

1. **用户认证**
   - 登录/登出
   - Session 管理

2. **项目管理**
   - 项目列表（搜索、筛选）
   - 创建项目
   - 项目详情查看
   - 项目信息编辑

3. **文件管理**
   - 文件上传（支持材料、配件、人工、物流成本表）
   - 文件自动解析
   - 文件详情查看
   - 数据校验
   - 文件下载

4. **成本计算**
   - 成本计算页面
   - 文件版本选择
   - 成本报告生成
   - Excel 报告下载

5. **审计日志**
   - 日志列表查看
   - 日志筛选和搜索

6. **用户管理**
   - 用户列表
   - 创建用户
   - 编辑用户信息
   - 重置密码
   - 启用/禁用用户

## 技术栈

- **后端**: Flask 2.3.3
- **前端**: Tailwind CSS + Alpine.js
- **图标**: Heroicons
- **数据库**: SQLite (通过 SQLAlchemy)

## 目录结构

```
price-caculation-system/
├── app/
│   ├── __init__.py          # Flask 应用工厂
│   ├── db/                   # 数据库相关
│   ├── models/              # 数据模型
│   ├── routes/              # 路由文件
│   │   ├── auth.py          # 认证路由
│   │   ├── project.py       # 项目路由
│   │   ├── file.py          # 文件路由
│   │   ├── report.py         # 报告路由
│   │   ├── audit.py          # 审计日志路由
│   │   └── user.py          # 用户管理路由
│   └── services/            # 业务逻辑服务
├── templates/                # Jinja2 模板
│   ├── base.html            # 基础模板
│   ├── auth/                # 认证相关模板
│   ├── project/             # 项目相关模板
│   ├── file/                # 文件相关模板
│   ├── report/              # 报告相关模板
│   ├── audit/               # 审计日志模板
│   └── user/                # 用户管理模板
├── uploads/                  # 文件上传目录
├── flask_session/           # Session 存储目录
├── run.py                   # 应用启动文件
└── requirements.txt         # Python 依赖

```

## 服务初始化顺序

根据 `draft/test.ipynb` 中的测试代码，服务的初始化顺序如下：

```python
db = SessionLocal()
audit_log_service = AuditLogService(db)
user_service = UserService(db)
name_normalization_service = NameNormalizationService(db, audit_log_service)
project_service = ProjectService(db, audit_log_service, name_normalization_service)
file_service = FileRecordService(db, audit_log_service)
excel_ingest_service = ExcelIngestService(db, audit_log_service, name_normalization_service, file_service)
validation_service = ValidationService(db, audit_log_service)
item_edit_service = ItemEditService(db, audit_log_service, validation_service)
cost_service = CostCalculationService(db, audit_log_service)
```

## 注意事项

1. **数据库路径**: 默认使用项目根目录下的 `cost_sys.db`
2. **文件上传**: 上传的文件存储在 `uploads/excel/` 目录
3. **Session 存储**: Session 文件存储在 `flask_session/` 目录
4. **服务依赖**: 确保按照正确的顺序初始化服务，特别是 `ExcelIngestService` 需要 `FileRecordService` 作为依赖

## 开发说明

- 所有业务逻辑都在 `app/services/` 目录中
- 路由文件在 `app/routes/` 目录中，负责处理 HTTP 请求和响应
- 模板文件在 `templates/` 目录中，使用 Jinja2 模板引擎
- UI 设计参考 `price-side/UI_DESIGN.md` 和 `price-side/USER_FLOW.md`

## 故障排除

如果遇到问题：

1. 检查数据库文件是否存在：`cost_sys.db`
2. 检查上传目录权限：`uploads/excel/`
3. 检查 Session 目录权限：`flask_session/`
4. 查看 Flask 日志输出

