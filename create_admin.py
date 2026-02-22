# app/db/create_admin.py
"""
创建初始管理员 / 示例用户
⚠️ 仅用于开发 / 手动维护
"""

from app.db.session import get_session
from app.services.user_service import UserService


def create_admin():
    db = get_session()
    try:
        user_service = UserService(db)

        users_to_create = [
            {
                "account": "admin",
                "password": "admin123",
                "display_name": "管理员",
                "email": "admin@example.com",
            },
            {
                "account": "account1",
                "password": "account1123",
                "display_name": "用户1",
                "email": "account1@example.com",
            },
            {
                "account": "account2",
                "password": "account2123",
                "display_name": "用户2",
                "email": "account2@example.com",
            },
        ]

        for u in users_to_create:
            existing = user_service.get_user_by_account(u["account"])
            if existing:
                print(f"⚠️ 用户 '{u['account']}' 已存在，跳过创建")
                continue

            user_service.create_user(
                account=u["account"],
                password=u["password"],
                display_name=u["display_name"],
                email=u["email"],
            )

        db.commit()
        print("✅ 初始管理员 / 用户创建完成")

    except Exception as e:
        db.rollback()
        print(f"❌ 创建失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
