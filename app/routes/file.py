# app/routes/file.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify,abort
from werkzeug.utils import secure_filename
import os
from app.db.session import get_session
from app.services.file_record_service import FileRecordService
from app.services.excel_ingest_service import ExcelIngestService
from app.services.validation_service import ValidationService
from app.services.audit_log_service import AuditLogService
from app.services.name_normalization_service import NameNormalizationService
from app.services.item_edit_service import ItemEditService
from app.models.file_record import FileRecord
from app.db.enums import FileType, ParseStatus, ValidationStatus,LogisticsType
from app import EXCEL_UPLOAD_FOLDER
from decimal import Decimal, InvalidOperation

file_bp = Blueprint('file', __name__, url_prefix='/projects/<project_id>/files')


def require_login():
    """检查登录状态"""
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))
    return None


def allowed_file(filename):
    """检查文件扩展名"""
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@file_bp.route('/upload', methods=['GET', 'POST'])
def upload_file(project_id):
    """文件上传页面"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        from app.models.project import Project
        project = db.query(Project).get(project_id)
        if not project:
            flash('项目不存在', 'error')
            return redirect(url_for('project.list_projects'))
        
        if request.method == 'POST':
            file_type_str = request.form.get('file_type')
            if not file_type_str:
                flash('请选择文件类型', 'error')
                return render_template('file/upload.html', project=project)
            
            try:
                file_type = FileType[file_type_str]
            except KeyError:
                flash('无效的文件类型', 'error')
                return render_template('file/upload.html', project=project)
            
            if 'file' not in request.files:
                flash('请选择文件', 'error')
                return render_template('file/upload.html', project=project)
            
            file = request.files['file']
            if file.filename == '' or not file.filename:
                flash('请选择文件', 'error')
                return render_template('file/upload.html', project=project)
            
            if not allowed_file(file.filename):
                flash('仅支持 .xlsx 和 .xls 格式', 'error')
                return render_template('file/upload.html', project=project)
            
            # 保存文件
            filename = secure_filename(file.filename)
            import time
            timestamp = str(int(time.time() * 1000))
            unique_filename = f"{project_id}_{file_type.value}_{timestamp}_{filename}"
            file_path = os.path.join(EXCEL_UPLOAD_FOLDER, unique_filename)
            file.save(file_path)
            
            # 读取文件字节（用于哈希）
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            
            # 创建文件记录
            audit_log_service = AuditLogService(db)
            file_service = FileRecordService(db, audit_log_service)
            
            file_record = file_service.create_update_file_record(
                project_id=project_id,
                file_type=file_type,
                original_name=filename,
                storage_path=file_path,
                file_bytes=file_bytes,
                operator_id=session['user_id']
            )
            
            # 如果不是 manual 类型，自动解析
            if file_type != FileType.manual:
                try:
                    name_normalization_service = NameNormalizationService(db, audit_log_service)
                    excel_ingest_service = ExcelIngestService(db, audit_log_service, name_normalization_service, file_service)
                    excel_ingest_service.ingest(file_record)
                    db.commit()
                    flash('文件上传并解析成功', 'success')
                    
                    # 解析成功后自动触发校验
                    try:
                        validation_service = ValidationService(db, audit_log_service)
                        validation_report = validation_service.validate_file(file_record)
                        db.commit()
                        if validation_report.blocked_count > 0:
                            flash(f'校验完成：发现 {validation_report.blocked_count} 个阻断项，{validation_report.warning_count} 个警告项，请及时处理', 'warning')
                        elif validation_report.warning_count > 0:
                            flash(f'校验完成：发现 {validation_report.warning_count} 个警告项，可以确认后继续', 'info')
                        else:
                            flash('校验完成：所有数据项正常', 'success')
                    except Exception as e:
                        # 校验失败不影响，用户可以在详情页手动触发
                        pass
                except Exception as e:
                    db.rollback()
                    flash(f'文件解析失败: {str(e)}', 'error')
            else:
                db.commit()
                flash('文件上传成功', 'success')
            
            return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_record.id))
        
        return render_template('file/upload.html', project=project)
    finally:
        db.close()


@file_bp.route('/<file_id>')
def file_detail(project_id, file_id):
    """文件详情页面"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        file_record = db.query(FileRecord).get(file_id)
        if not file_record or file_record.project_id != project_id:
            flash('文件不存在', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        # 获取筛选和搜索参数
        status_filter = request.args.get('status', 'all')
        search = request.args.get('search', '').strip()
        
        # 根据文件类型加载对应的数据项
        items = []
        if file_record.file_type == FileType.material_cost:
            from app.models.material_item import MaterialItem
            from app.db.enums import CostItemStatus
            query = db.query(MaterialItem).filter(
                MaterialItem.source_file_id == file_id
            )
            if status_filter != 'all':
                if status_filter == 'ok':
                    query = query.filter(MaterialItem.status == CostItemStatus.ok)
                elif status_filter == 'warning':
                    query = query.filter(MaterialItem.status == CostItemStatus.warning)
                elif status_filter == 'blocked':
                    query = query.filter(MaterialItem.status == CostItemStatus.blocked)
                elif status_filter == 'confirmed':
                    query = query.filter(MaterialItem.status == CostItemStatus.confirmed)
            if search:
                from sqlalchemy import or_
                query = query.filter(
                    or_(
                        MaterialItem.raw_name.contains(search),
                        MaterialItem.normalized_name.contains(search),
                        MaterialItem.spec.contains(search) if MaterialItem.spec else False
                    )
                )
            items = query.all()
        elif file_record.file_type == FileType.part_cost:
            from app.models.part_item import PartItem
            from app.db.enums import CostItemStatus
            query = db.query(PartItem).filter(
                PartItem.source_file_id == file_id
            )
            if status_filter != 'all':
                if status_filter == 'ok':
                    query = query.filter(PartItem.status == CostItemStatus.ok)
                elif status_filter == 'warning':
                    query = query.filter(PartItem.status == CostItemStatus.warning)
                elif status_filter == 'blocked':
                    query = query.filter(PartItem.status == CostItemStatus.blocked)
                elif status_filter == 'confirmed':
                    query = query.filter(PartItem.status == CostItemStatus.confirmed)
            if search:
                from sqlalchemy import or_
                query = query.filter(
                    or_(
                        PartItem.raw_name.contains(search),
                        PartItem.normalized_name.contains(search),
                        PartItem.spec.contains(search) if PartItem.spec else False
                    )
                )
            items = query.all()
        elif file_record.file_type == FileType.labor_cost:
            from app.models.labor_item import LaborItem
            from app.db.enums import CostItemStatus
            query = db.query(LaborItem).filter(
                LaborItem.source_file_id == file_id
            )
            if status_filter != 'all':
                if status_filter == 'ok':
                    query = query.filter(LaborItem.status == CostItemStatus.ok)
                elif status_filter == 'warning':
                    query = query.filter(LaborItem.status == CostItemStatus.warning)
                elif status_filter == 'blocked':
                    query = query.filter(LaborItem.status == CostItemStatus.blocked)
                elif status_filter == 'confirmed':
                    query = query.filter(LaborItem.status == CostItemStatus.confirmed)
            if search:
                from sqlalchemy import or_
                query = query.filter(
                    or_(
                        LaborItem.raw_group.contains(search),
                        LaborItem.normalized_group.contains(search)
                    )
                )
            items = query.all()
        elif file_record.file_type == FileType.logistics_cost:
            from app.models.logistics_item import LogisticsItem
            from app.db.enums import CostItemStatus
            query = db.query(LogisticsItem).filter(
                LogisticsItem.source_file_id == file_id
            )
            if status_filter != 'all':
                if status_filter == 'ok':
                    query = query.filter(LogisticsItem.status == CostItemStatus.ok)
                elif status_filter == 'warning':
                    query = query.filter(LogisticsItem.status == CostItemStatus.warning)
                elif status_filter == 'blocked':
                    query = query.filter(LogisticsItem.status == CostItemStatus.blocked)
                elif status_filter == 'confirmed':
                    query = query.filter(LogisticsItem.status == CostItemStatus.confirmed)
            if search:
                query = query.filter(LogisticsItem.description.contains(search))
            items = query.all()
        elif file_record.file_type == FileType.manual:
            # manual 类型的文件可能包含不同类型的 item，需要检测
            from app.models.material_item import MaterialItem
            from app.models.part_item import PartItem
            from app.models.labor_item import LaborItem
            from app.models.logistics_item import LogisticsItem
            from app.db.enums import CostItemStatus
            
            # 检测文件包含哪种类型的 item
            material_count = db.query(MaterialItem).filter(MaterialItem.source_file_id == file_id).count()
            part_count = db.query(PartItem).filter(PartItem.source_file_id == file_id).count()
            labor_count = db.query(LaborItem).filter(LaborItem.source_file_id == file_id).count()
            logistics_count = db.query(LogisticsItem).filter(LogisticsItem.source_file_id == file_id).count()
            
            # 根据实际包含的 item 类型加载数据
            if material_count > 0:
                query = db.query(MaterialItem).filter(MaterialItem.source_file_id == file_id)
                if status_filter != 'all':
                    if status_filter == 'ok':
                        query = query.filter(MaterialItem.status == CostItemStatus.ok)
                    elif status_filter == 'warning':
                        query = query.filter(MaterialItem.status == CostItemStatus.warning)
                    elif status_filter == 'blocked':
                        query = query.filter(MaterialItem.status == CostItemStatus.blocked)
                    elif status_filter == 'confirmed':
                        query = query.filter(MaterialItem.status == CostItemStatus.confirmed)
                if search:
                    from sqlalchemy import or_
                    query = query.filter(
                        or_(
                            MaterialItem.raw_name.contains(search),
                            MaterialItem.normalized_name.contains(search),
                            MaterialItem.spec.contains(search) if MaterialItem.spec else False
                        )
                    )
                items = query.all()
            elif part_count > 0:
                query = db.query(PartItem).filter(PartItem.source_file_id == file_id)
                if status_filter != 'all':
                    if status_filter == 'ok':
                        query = query.filter(PartItem.status == CostItemStatus.ok)
                    elif status_filter == 'warning':
                        query = query.filter(PartItem.status == CostItemStatus.warning)
                    elif status_filter == 'blocked':
                        query = query.filter(PartItem.status == CostItemStatus.blocked)
                    elif status_filter == 'confirmed':
                        query = query.filter(PartItem.status == CostItemStatus.confirmed)
                if search:
                    from sqlalchemy import or_
                    query = query.filter(
                        or_(
                            PartItem.raw_name.contains(search),
                            PartItem.normalized_name.contains(search),
                            PartItem.spec.contains(search) if PartItem.spec else False
                        )
                    )
                items = query.all()
            elif labor_count > 0:
                query = db.query(LaborItem).filter(LaborItem.source_file_id == file_id)
                if status_filter != 'all':
                    if status_filter == 'ok':
                        query = query.filter(LaborItem.status == CostItemStatus.ok)
                    elif status_filter == 'warning':
                        query = query.filter(LaborItem.status == CostItemStatus.warning)
                    elif status_filter == 'blocked':
                        query = query.filter(LaborItem.status == CostItemStatus.blocked)
                    elif status_filter == 'confirmed':
                        query = query.filter(LaborItem.status == CostItemStatus.confirmed)
                if search:
                    from sqlalchemy import or_
                    query = query.filter(
                        or_(
                            LaborItem.raw_group.contains(search),
                            LaborItem.normalized_group.contains(search)
                        )
                    )
                items = query.all()
            else:
                # 默认加载物流项（向后兼容）
                query = db.query(LogisticsItem).filter(LogisticsItem.source_file_id == file_id)
                if status_filter != 'all':
                    if status_filter == 'ok':
                        query = query.filter(LogisticsItem.status == CostItemStatus.ok)
                    elif status_filter == 'warning':
                        query = query.filter(LogisticsItem.status == CostItemStatus.warning)
                    elif status_filter == 'blocked':
                        query = query.filter(LogisticsItem.status == CostItemStatus.blocked)
                    elif status_filter == 'confirmed':
                        query = query.filter(LogisticsItem.status == CostItemStatus.confirmed)
                if search:
                    query = query.filter(LogisticsItem.description.contains(search))
                items = query.all()
        
        # 获取校验报告（如果有）
        validation_report = None
        if file_record.parse_status == ParseStatus.parsed:
            audit_log_service = AuditLogService(db)
            validation_service = ValidationService(db, audit_log_service)
            validation_report = validation_service.validate_file(file_record)
            db.commit()
        
        # 确定item类型用于路由
        if file_record.file_type == FileType.manual:
            # 检测 manual 文件包含的实际 item 类型
            from app.models.material_item import MaterialItem
            from app.models.part_item import PartItem
            from app.models.labor_item import LaborItem
            material_count = db.query(MaterialItem).filter(MaterialItem.source_file_id == file_id).count()
            part_count = db.query(PartItem).filter(PartItem.source_file_id == file_id).count()
            labor_count = db.query(LaborItem).filter(LaborItem.source_file_id == file_id).count()
            
            if material_count > 0:
                item_type = 'material'
            elif part_count > 0:
                item_type = 'part'
            elif labor_count > 0:
                item_type = 'labor'
            else:
                item_type = 'logistics'  # 默认
        else:
            file_type_map = {
                FileType.material_cost: 'material',
                FileType.part_cost: 'part',
                FileType.labor_cost: 'labor',
                FileType.logistics_cost: 'logistics',
            }
            item_type = file_type_map.get(file_record.file_type, 'material')
        
        # 创建item字典，便于模板中查找
        items_dict = {item.id: item for item in items}
        
        return render_template('file/detail.html', 
                             file_record=file_record,
                             items=items,
                             items_dict=items_dict,
                             validation_report=validation_report,
                             status_filter=status_filter,
                             search=search,
                             item_type=item_type)
    finally:
        db.close()


@file_bp.route('/<file_id>/validate', methods=['POST'])
def validate_file(project_id, file_id):
    """手动触发数据校验"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        file_record = db.query(FileRecord).get(file_id)
        if not file_record or file_record.project_id != project_id:
            flash('文件不存在', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        if file_record.parse_status != ParseStatus.parsed:
            flash('文件尚未解析，无法校验', 'error')
            return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
        
        audit_log_service = AuditLogService(db)
        validation_service = ValidationService(db, audit_log_service)
        validation_report = validation_service.validate_file(file_record)
        db.commit()
        
        flash(f'校验完成：正常 {validation_report.ok_count} 项，警告 {validation_report.warning_count} 项，阻断 {validation_report.blocked_count} 项', 'info')
        return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
    except Exception as e:
        db.rollback()
        flash(f'校验失败: {str(e)}', 'error')
        return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
    finally:
        db.close()


@file_bp.route('/<file_id>/items/<item_id>/edit', methods=['GET', 'POST'])
def edit_item(project_id, file_id, item_id):
    """编辑数据项"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        file_record = db.query(FileRecord).get(file_id)
        if not file_record or file_record.project_id != project_id:
            flash('文件不存在', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        if file_record.locked:
            flash('文件已锁定，无法编辑', 'error')
            return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
        
        # 确定item类型
        if file_record.file_type == FileType.manual:
            # 检测 manual 文件包含的实际 item 类型
            from app.models.material_item import MaterialItem
            from app.models.part_item import PartItem
            from app.models.labor_item import LaborItem
            material_count = db.query(MaterialItem).filter(MaterialItem.source_file_id == file_id).count()
            part_count = db.query(PartItem).filter(PartItem.source_file_id == file_id).count()
            labor_count = db.query(LaborItem).filter(LaborItem.source_file_id == file_id).count()
            
            if material_count > 0:
                item_type = 'material'
            elif part_count > 0:
                item_type = 'part'
            elif labor_count > 0:
                item_type = 'labor'
            else:
                item_type = 'logistics'  # 默认
        else:
            file_type_map = {
                FileType.material_cost: 'material',
                FileType.part_cost: 'part',
                FileType.labor_cost: 'labor',
                FileType.logistics_cost: 'logistics',
            }
            item_type = file_type_map.get(file_record.file_type)
        
        if not item_type:
            flash('不支持的文件类型', 'error')
            return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
        
        # 加载item
        if item_type == 'material':
            from app.models.material_item import MaterialItem
            item = db.query(MaterialItem).get(item_id)
        elif item_type == 'part':
            from app.models.part_item import PartItem
            item = db.query(PartItem).get(item_id)
        elif item_type == 'labor':
            from app.models.labor_item import LaborItem
            item = db.query(LaborItem).get(item_id)
        elif item_type == 'logistics':
            from app.models.logistics_item import LogisticsItem
            item = db.query(LogisticsItem).get(item_id)
        
        if not item or item.source_file_id != file_id:
            flash('数据项不存在', 'error')
            return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
        
        if request.method == 'POST':
            # 获取允许编辑的字段
            audit_log_service = AuditLogService(db)
            validation_service = ValidationService(db, audit_log_service)
            item_edit_service = ItemEditService(db, audit_log_service, validation_service)
            
            allowed_fields, _ = item_edit_service._allowed_edit_fields(item)
            
            # 构建更新字典
            updates = {}
            for field in allowed_fields:
                if field in request.form:
                    value = request.form.get(field)
                    if value == '':
                        updates[field] = None
                    else:
                        # 尝试转换为数字
                        try:
                            if field in ['quantity', 'unit_price', 'subtotal', 'weight_kg', 
                                       'work_quantity', 'extra_subsidies', 'ton_bonus']:
                                updates[field] = float(value)
                            else:
                                updates[field] = value
                        except ValueError:
                            updates[field] = value
            
            try:
                item_edit_service.edit_item(
                    item_type=item_type,
                    item_id=item_id,
                    updates=updates,
                    operator_id=session['user_id']
                )
                db.commit()
                flash('数据项更新成功', 'success')
                return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
            except Exception as e:
                db.rollback()
                flash(f'更新失败: {str(e)}', 'error')
                return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
        
        # GET 请求：显示编辑表单
        audit_log_service = AuditLogService(db)
        validation_service = ValidationService(db, audit_log_service)
        validation_report = None
        if file_record.parse_status == ParseStatus.parsed:
            validation_report = validation_service.validate_file(file_record)
        
        # 获取该项的校验结果
        item_result = None
        if validation_report and item_id in validation_report.item_results:
            item_result = validation_report.item_results[item_id]
        
        return render_template('file/edit_item.html',
                             file_record=file_record,
                             item=item,
                             item_type=item_type,
                             item_result=item_result)
    finally:
        db.close()


@file_bp.route('/<file_id>/items/<item_id>/confirm', methods=['POST'])
def confirm_item(project_id, file_id, item_id):
    """确认警告项"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        file_record = db.query(FileRecord).get(file_id)
        if not file_record or file_record.project_id != project_id:
            flash('文件不存在', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        if file_record.locked:
            flash('文件已锁定，无法确认', 'error')
            return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
        
        # 确定item类型
        if file_record.file_type == FileType.manual:
            # 检测 manual 文件包含的实际 item 类型
            from app.models.material_item import MaterialItem
            from app.models.part_item import PartItem
            from app.models.labor_item import LaborItem
            from app.models.logistics_item import LogisticsItem
            material_count = db.query(MaterialItem).filter(MaterialItem.source_file_id == file_id).count()
            part_count = db.query(PartItem).filter(PartItem.source_file_id == file_id).count()
            labor_count = db.query(LaborItem).filter(LaborItem.source_file_id == file_id).count()
            logistics_count = db.query(LogisticsItem).filter(LogisticsItem.source_file_id == file_id).count()
            
            if material_count > 0:
                item_type = 'material'
            elif part_count > 0:
                item_type = 'part'
            elif labor_count > 0:
                item_type = 'labor'
            elif logistics_count > 0:
                item_type = 'logistics'
            else:
                flash('无法确定数据项类型', 'error')
                return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
            
            # manual 类型的物流项不允许确认
            if item_type == 'logistics':
                flash('手动创建的物流项不允许确认', 'error')
                return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
        else:
            file_type_map = {
                FileType.material_cost: 'material',
                FileType.part_cost: 'part',
                FileType.labor_cost: 'labor',
                FileType.logistics_cost: 'logistics',
            }
            item_type = file_type_map.get(file_record.file_type)
        
        if not item_type:
            flash('不支持的文件类型', 'error')
            return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
        
        audit_log_service = AuditLogService(db)
        validation_service = ValidationService(db, audit_log_service)
        item_edit_service = ItemEditService(db, audit_log_service, validation_service)
        
        try:
            item_edit_service.confirm_warning_item(
                item_type=item_type,
                item_id=item_id,
                operator_id=session['user_id']
            )
            db.commit()
            flash('数据项已确认', 'success')
        except ValueError as e:
            db.rollback()
            flash(f'确认失败: {str(e)}', 'error')
        except Exception as e:
            db.rollback()
            flash(f'确认失败: {str(e)}', 'error')
        
        return redirect(url_for('file.file_detail', project_id=project_id, file_id=file_id))
    finally:
        db.close()


@file_bp.route('/<file_id>/download')
def download_file(project_id, file_id):
    """下载文件"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        file_record = db.query(FileRecord).get(file_id)
        if not file_record or file_record.project_id != project_id:
            flash('文件不存在', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        if not file_record.storage_path or not os.path.exists(file_record.storage_path):
            flash('文件不存在', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        return send_file(
            file_record.storage_path,
            as_attachment=True,
            download_name=file_record.original_name or 'file.xlsx'
        )
    finally:
        db.close()


@file_bp.route('/manual/<item_type>/add', methods=['GET', 'POST'])
def add_manual_item(project_id, item_type):
    """手工添加数据项"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        from app.models.project import Project
        project = db.query(Project).get(project_id)
        if not project:
            flash('项目不存在', 'error')
            return redirect(url_for('project.list_projects'))
        
        # 验证item_type
        valid_types = ['material', 'part', 'labor', 'logistics']
        if item_type not in valid_types:
            flash('无效的数据类型', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        if request.method == 'POST':
            try:
                audit_log_service = AuditLogService(db)
                name_normalization_service = NameNormalizationService(db, audit_log_service)
                file_service = FileRecordService(db, audit_log_service)
                excel_ingest_service = ExcelIngestService(db, audit_log_service, name_normalization_service, file_service)
                
                if item_type == 'material':
                    abort(403)
                    raw_name = request.form.get('raw_name', '').strip()
                    if not raw_name:
                        flash('材料名称不能为空', 'error')
                        return render_template('file/add_manual_item.html', project=project, item_type=item_type)
                    
                    material_file, material_item = excel_ingest_service.parse_manual_material_item(
                        project_id=project_id,
                        raw_name=raw_name,
                        operator_id=session['user_id'],
                        spec=request.form.get('spec', '').strip() or None,
                        quantity=float(request.form.get('quantity')) if request.form.get('quantity') else None,
                        unit=request.form.get('unit', '').strip() or None,
                        material_grade=request.form.get('material_grade', '').strip() or None,
                        weight_kg=float(request.form.get('weight_kg')) if request.form.get('weight_kg') else None,
                        unit_price=float(request.form.get('unit_price')) if request.form.get('unit_price') else None,
                        subtotal=float(request.form.get('subtotal')) if request.form.get('subtotal') else None,
                        supplier=request.form.get('supplier', '').strip() or None,
                    )
                    db.commit()
                    flash('材料添加成功', 'success')
                    return redirect(url_for('file.file_detail', project_id=project_id, file_id=material_file.id))
                
                elif item_type == 'part':
                    abort(403)
                    raw_name = request.form.get('raw_name', '').strip()
                    if not raw_name:
                        flash('配件名称不能为空', 'error')
                        return render_template('file/add_manual_item.html', project=project, item_type=item_type)
                    
                    part_file, part_item = excel_ingest_service.parse_manual_part_item(
                        project_id=project_id,
                        raw_name=raw_name,
                        operator_id=session['user_id'],
                        spec=request.form.get('spec', '').strip() or None,
                        quantity=float(request.form.get('quantity')) if request.form.get('quantity') else None,
                        unit=request.form.get('unit', '').strip() or None,
                        unit_price=float(request.form.get('unit_price')) if request.form.get('unit_price') else None,
                        subtotal=float(request.form.get('subtotal')) if request.form.get('subtotal') else None,
                        supplier=request.form.get('supplier', '').strip() or None,
                    )
                    db.commit()
                    flash('配件添加成功', 'success')
                    return redirect(url_for('file.file_detail', project_id=project_id, file_id=part_file.id))
                
                elif item_type == 'labor':
                    abort(403)
                    raw_group = request.form.get('raw_group', '').strip()
                    if not raw_group:
                        flash('班组名称不能为空', 'error')
                        return render_template('file/add_manual_item.html', project=project, item_type=item_type)
                    
                    labor_file, labor_item = excel_ingest_service.parse_manual_labor_item(
                        project_id=project_id,
                        raw_group=raw_group,
                        operator_id=session['user_id'],
                        work_quantity=float(request.form.get('work_quantity')) if request.form.get('work_quantity') else None,
                        unit=request.form.get('unit', '').strip() or None,
                        unit_price=float(request.form.get('unit_price')) if request.form.get('unit_price') else None,
                        extra_subsidies=float(request.form.get('extra_subsidies')) if request.form.get('extra_subsidies') else None,
                        ton_bonus=float(request.form.get('ton_bonus')) if request.form.get('ton_bonus') else None,
                        subtotal=float(request.form.get('subtotal')) if request.form.get('subtotal') else None,
                    )
                    db.commit()
                    flash('人工成本项添加成功', 'success')
                    return redirect(url_for('file.file_detail', project_id=project_id, file_id=labor_file.id))
                
                elif item_type == 'logistics':
                    logistics_type = request.form.get("type")
                    if not logistics_type:
                        flash('类型不能为空', 'error')
                        return render_template('file/add_manual_item.html', project=project, item_type=item_type,form_data=request.form)
                    
                    description = request.form.get('description', '').strip()
                    if not description:
                        flash('备注描述不能为空', 'error')
                        return render_template('file/add_manual_item.html', project=project, item_type=item_type,form_data=request.form)
                    
                    subtotal = request.form.get('subtotal')
                    if not subtotal:
                        flash('小计金额不能为空', 'error')
                        return render_template('file/add_manual_item.html', project=project, item_type=item_type,form_data=request.form)
                    try:
                        subtotal = Decimal(subtotal)
                    except (InvalidOperation, TypeError):
                        flash('小计金额格式错误', 'error')
                        return render_template('file/add_manual_item.html', project=project, item_type=item_type,form_data=request.form)
                    
                    logistics_file, logistics_item = excel_ingest_service.parse_manual_logistics_item(
                        project_id=project_id,
                        type=str(logistics_type),
                        description=description,
                        subtotal=float(subtotal),
                        operator_id=session['user_id']
                    )
                    db.commit()
                    flash('物流成本项添加成功', 'success')
                    return redirect(url_for('file.file_detail', project_id=project_id, file_id=logistics_file.id))
                
            except ValueError as e:
                db.rollback()
                flash(f'添加失败: {str(e)}', 'error')
            except Exception as e:
                db.rollback()
                flash(f'添加失败: {str(e)}', 'error')
        
        return render_template('file/add_manual_item.html', project=project, item_type=item_type)
    finally:
        db.close()

