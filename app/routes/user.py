# app/routes/user.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.db.session import get_session
from app.services.user_service import UserService
from app.models.user import User

user_bp = Blueprint('user', __name__, url_prefix='/users')


def require_login():
    """检查登录状态"""
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))
    return None


def require_admin():
    """检查管理员权限（简化版，V0.1 可以所有登录用户访问）"""
    check = require_login()
    if check:
        return check
    # TODO: 实现真正的权限检查
    return None


@user_bp.route('')
def list_users():
    """用户列表（管理员）"""
    check = require_admin()
    if check:
        return check
    
    db = get_session()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        return render_template('user/list.html', users=users)
    finally:
        db.close()


@user_bp.route('/create', methods=['GET', 'POST'])
def create_user():
    """创建用户（管理员）"""
    check = require_admin()
    if check:
        return check
    
    if request.method == 'POST':
        account = request.form.get('account', '').strip()
        password = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip() or None
        email = request.form.get('email', '').strip() or None
        phone_number = request.form.get('phone_number', '').strip() or None
        
        if not account or not password:
            flash('账号和密码不能为空', 'error')
            return render_template('user/create.html')
        
        db = get_session()
        try:
            user_service = UserService(db)
            user = user_service.create_user(
                account=account,
                password=password,
                display_name=display_name,
                email=email,
                phone_number=phone_number
            )
            db.commit()
            flash('用户创建成功', 'success')
            return redirect(url_for('user.list_users'))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            db.rollback()
            flash(f'创建失败: {str(e)}', 'error')
        finally:
            db.close()
    
    return render_template('user/create.html')


@user_bp.route('/<user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    """编辑用户（管理员）"""
    check = require_admin()
    if check:
        return check
    
    db = get_session()
    try:
        user = db.query(User).get(user_id)
        if not user:
            flash('用户不存在', 'error')
            return redirect(url_for('user.list_users'))
        
        if request.method == 'POST':
            display_name = request.form.get('display_name', '').strip() or None
            email = request.form.get('email', '').strip() or None
            phone_number = request.form.get('phone_number', '').strip() or None
            
            user.display_name = display_name
            user.email = email
            user.phone_number = phone_number
            
            db.commit()
            flash('用户信息更新成功', 'success')
            return redirect(url_for('user.list_users'))
        
        return render_template('user/edit.html', user=user)
    finally:
        db.close()


@user_bp.route('/<user_id>/reset-password', methods=['POST'])
def reset_password(user_id):
    """重置密码（管理员）"""
    check = require_admin()
    if check:
        return check
    
    new_password = request.form.get('new_password', '')
    if not new_password:
        flash('新密码不能为空', 'error')
        return redirect(url_for('user.list_users'))
    
    db = get_session()
    try:
        user_service = UserService(db)
        user_service.reset_password(user_id=user_id, new_password=new_password)
        db.commit()
        flash('密码重置成功', 'success')
    except Exception as e:
        db.rollback()
        flash(f'重置失败: {str(e)}', 'error')
    finally:
        db.close()
    
    return redirect(url_for('user.list_users'))


@user_bp.route('/<user_id>/toggle-status', methods=['POST'])
def toggle_user_status(user_id):
    """切换用户状态（启用/禁用）"""
    check = require_admin()
    if check:
        return check
    
    db = get_session()
    try:
        user = db.query(User).get(user_id)
        if not user:
            flash('用户不存在', 'error')
            return redirect(url_for('user.list_users'))
        
        user.is_active = not user.is_active
        db.commit()
        
        status = '启用' if user.is_active else '禁用'
        flash(f'用户已{status}', 'success')
    except Exception as e:
        db.rollback()
        flash(f'操作失败: {str(e)}', 'error')
    finally:
        db.close()
    
    return redirect(url_for('user.list_users'))

