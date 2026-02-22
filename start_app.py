'''
start_app.py 是 桌面发行版的启动器（Launcher）/ EXE 外壳
用户点击应用后触发，先设置校验环境变量，再通过run.py启动 Flask 服务
不该：
写 Flask 路由
操作 SQLAlchemy
业务逻辑
修改 app 配置结构
'''

import time
import socket
import webbrowser
import sys
import os
import ctypes
import configparser
import threading


def show_error(title, message):
    ctypes.windll.user32.MessageBoxW(0, message, 0x10)


def is_port_in_use(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def get_runtime_dir():
    """
    exe：exe 所在目录
    dev：当前文件目录
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ===== 基础路径 =====
BASE_DIR = get_runtime_dir()

# ===== 配置文件校验 =====
config_path = os.path.join(BASE_DIR, "config.ini")
if not os.path.exists(config_path):
    show_error(
        "配置错误",
        f"未找到 config.ini\n\n请确认 config.ini 与程序放在同一目录：\n{BASE_DIR}"
    )
    sys.exit(1)

config = configparser.ConfigParser()
config.read(config_path, encoding="utf-8")

PORT = config.getint("server", "port", fallback=5000)
OPEN_BROWSER = config.getboolean("browser", "open_url", fallback=True)

# ===== 数据库校验（极其关键）=====
DB_PATH = os.path.join(BASE_DIR, "cost_sys.db")
if not os.path.exists(DB_PATH):
    show_error(
        "数据库缺失",
        f"未找到 cost_sys.db\n\n请确认数据库文件与程序放在同一目录：\n{BASE_DIR}"
    )
    sys.exit(1)

# ===== 在 import run 之前，锁死数据库路径 =====
# 这一步非常关键，必须在任何可能导入数据库的模块之前执行,如run.py
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

# ===== 端口占用 =====
if is_port_in_use("127.0.0.1", PORT):
    show_error("系统已运行", f"端口 {PORT} 已被占用")
    sys.exit(0)


def wait_for_server(port, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


# ===== 延迟 import（关键修复点）=====
def start_flask():
    from run import main
    main()


# ===== Flask 启动多线程 =====
flask_thread = threading.Thread(target=start_flask)
flask_thread.start()

if not wait_for_server(PORT):
    show_error("启动失败", "Flask 服务启动失败")
    sys.exit(1)

if OPEN_BROWSER:
    webbrowser.open(f"http://127.0.0.1:{PORT}/login")

flask_thread.join()
