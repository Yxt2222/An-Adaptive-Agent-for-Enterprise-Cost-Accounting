"""
数据库自动初始化检查模块
在应用启动时自动检查并执行必要的初始化步骤
"""
from sqlalchemy import inspect
from app.db.session import get_engine, get_session
from app.db.init_db import init_db
from app.services.user_service import UserService
#-------------------导入所有表-----------------------
from app.models.user import User
from app.models.project import Project
from app.models.file_record import FileRecord
from app.models.material_item import MaterialItem
from app.models.part_item import PartItem
from app.models.labor_item import LaborItem
from app.models.logistics_item import LogisticsItem
from app.models.cost_summary import CostSummary
from app.models.name_mapping import NameMapping
from app.models.audit_log import AuditLog
from app.models.raw_upload_record import RawUploadRecord

def check_tables_exist() -> bool:
    """检查数据库表是否存在"""
    try:
        engine = get_engine()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return "users" in tables
    except Exception as e:
        print(f"⚠️ 检查数据库表失败: {e}")
        return False


def check_admin_user_exists() -> bool:
    """检查管理员用户是否存在"""
    db = get_session()
    try:
        user_service = UserService(db)
        admin_user = user_service.get_user_by_account("admin")
        return admin_user is not None
    except Exception as e:
        print(f"⚠️ 检查管理员用户失败: {e}")
        return False
    finally:
        db.close()


def create_admin_user():
    """创建管理员用户"""
    db = get_session()
    try:
        user_service = UserService(db)

        existing_user = user_service.get_user_by_account("admin")
        if existing_user:
            print("ℹ️  管理员用户已存在，跳过创建")
            return

        user_service.create_user(
            account="admin",
            password="admin123",
            display_name="管理员",
            email="admin@example.com",
        )

        db.commit()
        print("✅ 管理员用户创建成功!")
        print("   账号: admin")
        print("   密码: admin123")
        print("   ⚠️  请登录后立即修改密码！")

    except Exception as e:
        db.rollback()
        print(f"❌ 创建管理员用户失败: {e}")
        raise
    finally:
        db.close()


def auto_init():
    """
    自动初始化检查
    如果数据库未初始化或缺少管理员用户，自动执行初始化
    """
    print("🔍 检查数据库初始化状态...")

    if not check_tables_exist():
        print("📦 数据库表不存在，正在创建...")
        try:
            init_db()  # ⚠️ init_db 内部也必须用 get_engine()
            print("✅ 数据库表创建成功")
        except Exception as e:
            print(f"❌ 数据库表创建失败: {e}")
            raise
    else:
        print("✅ 数据库表已存在")

    if not check_admin_user_exists():
        print("👤 管理员用户不存在，正在创建...")
        try:
            create_admin_user()
        except Exception as e:
            print(f"❌ 创建管理员用户失败: {e}")
            raise
    else:
        print("✅ 管理员用户已存在")

    print("🎉 数据库初始化检查完成\n")


if __name__ == "__main__":
    auto_init()
