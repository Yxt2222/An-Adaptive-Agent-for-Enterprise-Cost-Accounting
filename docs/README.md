# 核价系统

核价系统是一个用于管理项目成本计算的 Web 应用系统。

## 快速开始

### 1. 安装依赖

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

## 功能特性

- ✅ **自动初始化**: 首次运行自动完成数据库和用户初始化
- ✅ **项目管理**: 创建、编辑、查看项目
- ✅ **文件管理**: 上传 Excel 文件，自动解析和校验
- ✅ **成本计算**: 自动计算项目成本，生成报告
- ✅ **审计日志**: 完整的操作审计追踪
- ✅ **用户管理**: 用户创建、编辑、权限管理

## 技术栈

- **后端**: Flask 2.3.3
- **前端**: Tailwind CSS + Alpine.js
- **数据库**: SQLite (通过 SQLAlchemy)
- **图标**: Heroicons

## 目录结构

```
price-caculation-system/
├── app/
│   ├── __init__.py          # Flask 应用工厂
│   ├── db/                   # 数据库相关
│   │   ├── auto_init.py      # 自动初始化检查
│   │   ├── init_db.py        # 数据库初始化
│   │   └── session.py        # 数据库会话
│   ├── models/              # 数据模型
│   ├── routes/              # 路由文件
│   └── services/            # 业务逻辑服务
├── templates/                # Jinja2 模板
├── uploads/                  # 文件上传目录
├── flask_session/           # Session 存储目录
├── run.py                   # 应用启动文件（含自动初始化）
└── requirements.txt         # Python 依赖
```

## 开发说明

### 服务初始化顺序

根据 `draft/test.ipynb`，服务的初始化顺序如下：

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

### 环境变量

可以通过环境变量配置：

- `HOST`: 服务器地址（默认: `0.0.0.0`）
- `PORT`: 服务器端口（默认: `5000`）
- `FLASK_DEBUG`: 调试模式（默认: `False`）
- `SECRET_KEY`: Flask 密钥（默认: 开发密钥）
- `DATABASE_URL`: 数据库 URL（默认: SQLite）
- `MAX_UPLOAD_SIZE`: 最大上传文件大小（默认: 10MB）

## 故障排除

### 数据库问题

如果遇到数据库相关错误：

1. 检查数据库文件是否存在：`cost_sys.db`
2. 手动运行初始化：
   ```bash
   python app/db/auto_init.py
   ```

### 依赖问题

如果遇到模块导入错误：

```bash
pip install -r requirements.txt
```

### 权限问题

确保以下目录有写入权限：
- `uploads/excel/` - 文件上传目录
- `flask_session/` - Session 存储目录

## 更多信息

- 详细功能说明: 参考 `PRD.md`
- UI 设计文档: 参考 `price-side/UI_DESIGN.md`
- 用户流程文档: 参考 `price-side/USER_FLOW.md`
