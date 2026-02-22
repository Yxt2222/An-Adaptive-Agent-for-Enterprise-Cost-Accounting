# run.py
"""
run.py
run.py 是标准 Flask 服务启动脚本（给开发者 / 运维 / CLI 用）
仅用于本地 / 内网启动 Flask 服务
打包 / GUI 启动请通过 start_app.py
"""
import os
import sys
from flask import request
from app.app_factory import create_app
from app.db.auto_init import auto_init


def get_app_base_dir():
    """
    获取程序根目录
    - 开发态：run.py 所在目录
    - PyInstaller：exe 所在目录
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))


def configure_database():
    """
    强制指定数据库为：程序根目录下的 cost_sys.db
    """
    base_dir = get_app_base_dir()
    db_path = os.path.join(base_dir, "cost_sys.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"#锁死数据库路径，防止打包后路径错乱
    print(f"📦 Using database: {db_path}")


def register_shutdown(app):
    @app.route("/shutdown", methods=["POST"])
    def shutdown():
        func = request.environ.get("werkzeug.server.shutdown")
        if func:
            func()
        return "Shutting down..."


def main():
    # 0️统一数据库路径（最重要）
    configure_database()

    # 1️启动前初始化数据库
    auto_init()

    # 2️创建 Flask app
    app = create_app()

    print("DB URI:", app.config["SQLALCHEMY_DATABASE_URI"])
    print(app.url_map)

    # 3️注册 shutdown 路由
    register_shutdown(app)

    # 4️启动参数
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    debug = True

    # 5️启动服务
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    main()
