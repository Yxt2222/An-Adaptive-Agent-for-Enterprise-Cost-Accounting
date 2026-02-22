# 初始化步骤

## 完整初始化流程

### 1. 安装依赖

```bash
cd price-caculation-system
pip install -r requirements.txt
```

### 2. 初始化数据库（创建表结构）

```bash
cd price-caculation-system
python -c "from app.db.init_db import init_db; init_db(); print('✅ Database tables created')"
```

或者直接运行：

```bash
cd price-caculation-system
python app/db/init_db.py
```

### 3. 创建管理员用户

```bash
cd price-caculation-system
python create_admin.py
```

默认管理员账号：
- **账号**: `admin`
- **密码**: `admin123`

⚠️ **重要**: 登录后请立即修改密码！**

### 4. 启动应用

```bash
cd price-caculation-system
python run.py
```

然后访问 `http://localhost:5000` 并使用 admin/admin123 登录。

## 如果遇到 "ModuleNotFoundError: No module named 'flask'"

说明依赖没有安装，请先执行：

```bash
cd price-caculation-system
pip install -r requirements.txt
```

## 如果数据库已存在但需要重新初始化

如果需要清空数据库重新开始：

```bash
cd price-caculation-system
# 备份现有数据库（可选）
mv cost_sys.db cost_sys.db.backup

# 重新初始化
python -c "from app.db.init_db import init_db; init_db(); print('✅ Database tables created')"
python create_admin.py
```

## 验证初始化是否成功

运行以下命令检查：

```bash
cd price-caculation-system
python -c "from app.db.session import get_session; from app.models.user import User; db = get_session()(); users = db.query(User).all(); print(f'✅ 数据库中有 {len(users)} 个用户'); [print(f'  - {u.account}') for u in users]; db.close()"
```

