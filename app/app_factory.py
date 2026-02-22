'''“组装 Flask App 的工厂”（不启动，不产生“行为副作用）
app_factory.py 是 “可复用、可测试、无副作用的 Flask 装配层，负责把Flask示例拼接好，注入配置，注册蓝图，初始化session，注册error handler等，但不负责启动服务（不调用 app.run()
会被run.py，gunicorn.uwsgi/单元测试/未来worker/agent调用'''
# app/app_factory.py
from flask import Flask
from flask_session import Session
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取项目根目录（使用绝对路径）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 创建上传目录
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
EXCEL_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'excel')
os.makedirs(EXCEL_UPLOAD_FOLDER, exist_ok=True)


def create_app(config_name='development'):
    """应用工厂函数"""
    # 获取项目根目录（使用已定义的 BASE_DIR）
    template_dir = os.path.join(BASE_DIR, 'templates')
    static_dir = os.path.join(BASE_DIR, 'static')
    
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir if os.path.exists(static_dir) else None)
    
    # 基础配置
    # 确保 SECRET_KEY 是字符串类型（不是 bytes）
    secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    if isinstance(secret_key, bytes):
        secret_key = secret_key.decode('utf-8')
    app.config['SECRET_KEY'] = secret_key
    
    # 数据库配置（使用绝对路径）
    db_path = os.path.join(BASE_DIR, 'cost_sys.db')
    default_db_url = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', default_db_url)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 文件上传配置
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['EXCEL_UPLOAD_FOLDER'] = EXCEL_UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_SIZE', 10485760))  # 10MB
    
    # Session 配置
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_KEY_PREFIX'] = 'cost_sys:'
    # Session 文件存储目录（使用绝对路径）
    session_dir = os.path.join(BASE_DIR, 'flask_session')
    os.makedirs(session_dir, exist_ok=True)
    app.config['SESSION_FILE_DIR'] = session_dir
    
    # 初始化 Session
    Session(app)
    
    # 注册蓝图
    from app.routes.auth import auth_bp
    from app.routes.project import project_bp
    from app.routes.file import file_bp
    from app.routes.report import report_bp
    from app.routes.audit import audit_bp
    from app.routes.user import user_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(project_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(user_bp)
    
    # 注册错误处理
    register_error_handlers(app)
    
    return app


def register_error_handlers(app):
    """注册错误处理器"""
    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        return render_template('errors/500.html'), 500

 