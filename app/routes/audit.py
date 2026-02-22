# app/routes/audit.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session,abort
from app.presentation.constants import ACTION_COLOR_MAP
from app.db.session import get_session
from app.models.audit_log import AuditLog
from sqlalchemy import desc, or_,and_
from datetime import datetime, timedelta
from app.db.enums import AuditAction
from datetime import timezone
import traceback
 

audit_bp = Blueprint('audit', __name__, url_prefix='/audit-logs')


def require_login():
    """检查登录状态"""
    if 'user_id' not in session:
        abort(401)


@audit_bp.route('/')
def list_logs():
    """审计日志列表"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        # 获取筛选参数
        project_id = request.args.get('project_id', '').strip() or None
        user_id = request.args.get('user_id', '').strip() or None
        action = request.args.get('action', '').strip() or None#action 是 Enum
        start_date = request.args.get('start_date', '').strip() or None
        end_date = request.args.get('end_date', '').strip() or None
        search = request.args.get('search', '').strip()
        page = int(request.args.get('page', 1))
        per_page = 50
        
        # 构建查询
        query = db.query(AuditLog)
        
        if project_id:
            query = query.filter(AuditLog.project_id == project_id)
        
        if user_id:
            query = query.filter(AuditLog.operator_id == user_id)
        
        if action:
            try:
                query = query.filter(AuditLog.action == AuditAction(action))
            except ValueError:
                abort(400, "Invalid action")
        
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(AuditLog.timestamp >= start_dt)
            except:
                pass
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(AuditLog.timestamp < end_dt)
            except:
                pass
        
        if search:
            # AuditLog 没有 details 字段，搜索改为在多个字段中搜索
            from sqlalchemy import or_, cast, String, func
            search_str = str(search).strip()
            if search_str:
                # 在 changed_attribute, entity_id 中搜索（字符串字段）
                # JSON 字段和枚举字段不直接搜索，避免类型错误
                if len(search_str) >= 2:
                    query = query.filter(
                        or_(
                            cast(AuditLog.changed_attribute, String).contains(search_str),
                            cast(AuditLog.entity_id, String).contains(search_str)
                        )
                    )
        
        # 分页
        try:
            total = query.count()
        except Exception:
            total = 0


        logs = query.order_by(desc(AuditLog.timestamp)).offset((page - 1) * per_page).limit(per_page).all()
        
        # 获取项目列表（用于筛选）
        from app.models.project import Project
        projects = db.query(Project).order_by(Project.raw_name).all()
        
        # 获取用户列表（用于筛选）
        from app.models.user import User
        users = db.query(User).order_by(User.account).all()
        
        return render_template('audit/list.html',
                             logs=logs,
                             projects=projects,
                             users=users,
                             total=total,
                             page=page,
                             per_page=per_page,
                             project_id=project_id,
                             user_id=user_id,
                             action=action,
                             start_date=start_date,
                             end_date=end_date,
                             search=search,
                             action_color_map = ACTION_COLOR_MAP)
    except Exception as e:
        traceback.print_exc()
        raise
    finally:
        db.close()

