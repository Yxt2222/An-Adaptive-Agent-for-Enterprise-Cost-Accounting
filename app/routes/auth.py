# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.db.session import get_session
from app.services.user_service import UserService
from app.services.audit_log_service import AuditLogService

auth_bp = Blueprint('auth', __name__, url_prefix='')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        account = request.form.get('account', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        if not account or not password:
            flash('请输入账号和密码', 'error')
            return render_template('auth/login.html')
        
        db = get_session()
        try:
            user_service = UserService(db)
            user = user_service.authenticate(account=account, password=password)
            
            # 登录成功，设置 session
            session['user_id'] = user.id
            session['user_account'] = user.account
            session['user_name'] = user.display_name or user.account
            session.permanent = remember
            
            # 记录登录日志
            from app.db.enums import AuditEntityType
            audit_log_service = AuditLogService(db)
            audit_log_service.record_create(
                project_id=None,
                entity_type=AuditEntityType.User,
                entity_id=user.id,
                operator_id=user.id,
            )
            
            db.commit()
            
            flash('登录成功', 'success')
            return redirect(url_for('project.list_projects'))
            
        except ValueError as e:
            flash('账号或密码错误', 'error')
        except PermissionError as e:
            flash('账号已被禁用，请联系管理员', 'error')
        except Exception as e:
            flash(f'登录失败: {str(e)}', 'error')
        finally:
            db.close()
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """登出"""
    user_id = session.get('user_id')
    if user_id:
        db = get_session()
        try:
            from app.db.enums import AuditEntityType
            audit_log_service = AuditLogService(db)
            audit_log_service.record_create(
                project_id=None,
                entity_type=AuditEntityType.User,
                entity_id=user_id,
                operator_id=user_id,
            )
            db.commit()
        except:
            pass
        finally:
            db.close()
    
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/')
def index():
    """首页重定向"""
    if 'user_id' in session:
        return redirect(url_for('project.list_projects'))
    return redirect(url_for('auth.login'))

