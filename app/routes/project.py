# app/routes/project.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file, current_app
from app.db.session import get_session
from app.services.project_service import ProjectService
from app.services.file_record_service import FileRecordService
from app.services.cost_calculation_service import CostCalculationService
from app.services.audit_log_service import AuditLogService
from app.services.name_normalization_service import NameNormalizationService
from app.models.project import Project
from app.models.file_record import FileRecord
from app.models.cost_summary import CostSummary
from app.db.enums import FileType, CostSummaryStatus, ValidationStatus, ParseStatus
from sqlalchemy import desc
import pandas as pd
import io

project_bp = Blueprint('project', __name__, url_prefix='/projects')


def require_login():
    """检查登录状态"""
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))
    return None


@project_bp.route('/', methods=['GET'])
def list_projects():
    """项目列表页面"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        # 获取搜索和筛选参数
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', 'all')
        
        # 查询项目
        query = db.query(Project)

        if search:
            # 确保 search 是字符串类型
            search_str = str(search).strip() if search else ''
            if search_str:
                # 处理可能的 None 值，使用 or_ 和 isnot(None) 条件
                from sqlalchemy import or_
                query = query.filter(
                    or_(
                        Project.raw_name.contains(search_str),
                        (Project.business_code.isnot(None)) & (Project.business_code.contains(search_str)),
                        (Project.contract_code.isnot(None)) & (Project.contract_code.contains(search_str))
                    )
                )
        
        # 按更新时间倒序
        projects = query.order_by(desc(Project.updated_at)).all()
        
        # 获取每个项目的文件状态
        project_data = []
        audit_log_service = AuditLogService(db)
        file_service = FileRecordService(db, audit_log_service)
        
        for project in projects:
            # 获取各类型文件的最新版本
            material_file = file_service.get_latest_valid_file(
                project_id=project.id,
                file_type=FileType.material_cost
            )
            part_file = file_service.get_latest_valid_file(
                project_id=project.id,
                file_type=FileType.part_cost
            )
            labor_file = file_service.get_latest_valid_file(
                project_id=project.id,
                file_type=FileType.labor_cost
            )
            logistics_file = file_service.get_latest_valid_file(
                project_id=project.id,
                file_type=FileType.logistics_cost
            )
            
            # 获取最新成本报告
            latest_report = db.query(CostSummary).filter(
                CostSummary.project_id == project.id,
                CostSummary.status == CostSummaryStatus.ACTIVE
            ).order_by(desc(CostSummary.calculation_version)).first()
            
            project_data.append({
                'project': project,
                'material_file': material_file,
                'part_file': part_file,
                'labor_file': labor_file,
                'logistics_file': logistics_file,
                'has_report': latest_report is not None,
            })
        
        return render_template('project/list.html', projects=project_data, search=search, status_filter=status_filter)
    finally:
        db.close()


@project_bp.route('/create', methods=['GET', 'POST'])
def create_project():
    """创建项目"""
    check = require_login()
    if check:
        return check
    
    if request.method == 'POST':
        raw_name = request.form.get('raw_name', '').strip()
        business_code = request.form.get('business_code', '').strip() or None
        contract_code = request.form.get('contract_code', '').strip() or None
        spec_tags_str = request.form.get('spec_tags', '').strip()
        spec_tags = [tag.strip() for tag in spec_tags_str.split(',') if tag.strip()] if spec_tags_str else None
        
        if not raw_name:
            flash('项目名称不能为空', 'error')
            return render_template('project/create.html')
        
        db = get_session()
        try:
            audit_log_service = AuditLogService(db)
            name_normalization_service = NameNormalizationService(db, audit_log_service)
            project_service = ProjectService(db, audit_log_service, name_normalization_service)
            
            project = project_service.create_project(
                raw_name=raw_name,
                business_code=business_code,
                contract_code=contract_code,
                spec_tags=spec_tags,
                operator_id=session['user_id']
            )
            
            db.commit()
            flash('项目创建成功', 'success')
            return redirect(url_for('project.detail', project_id=project.id))
        except Exception as e:
            db.rollback()
            flash(f'创建项目失败: {str(e)}', 'error')
        finally:
            db.close()
    
    return render_template('project/create.html')


@project_bp.route('/<project_id>')
def detail(project_id):
    """项目详情页面"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        project = db.query(Project).get(project_id)
        if not project:
            flash('项目不存在', 'error')
            return redirect(url_for('project.list_projects'))
        
        audit_log_service = AuditLogService(db)
        file_service = FileRecordService(db, audit_log_service)
        
        # 获取各类型文件的最新版本
        material_file = file_service.get_latest_valid_file(
            project_id=project_id,
            file_type=FileType.material_cost
        )
        part_file = file_service.get_latest_valid_file(
            project_id=project_id,
            file_type=FileType.part_cost
        )
        labor_file = file_service.get_latest_valid_file(
            project_id=project_id,
            file_type=FileType.labor_cost
        )
        logistics_file = file_service.get_latest_valid_file(
            project_id=project_id,
            file_type=FileType.logistics_cost
        )
        
        # 获取所有文件版本（用于版本管理）
        material_files = file_service.list_file_records(
            project_id=project_id,
            file_type=FileType.material_cost
        )
        part_files = file_service.list_file_records(
            project_id=project_id,
            file_type=FileType.part_cost
        )
        labor_files = file_service.list_file_records(
            project_id=project_id,
            file_type=FileType.labor_cost
        )
        logistics_files = file_service.list_file_records(
            project_id=project_id,
            file_type=FileType.logistics_cost
        ) 
        # 获取最新成本报告
        latest_report = db.query(CostSummary).filter(
            CostSummary.project_id == project_id,
            CostSummary.status == CostSummaryStatus.ACTIVE
        ).order_by(desc(CostSummary.calculation_version)).first()
        
        # 获取所有历史报告
        all_reports = db.query(CostSummary).filter(
            CostSummary.project_id == project_id
        ).order_by(desc(CostSummary.calculation_version)).all()
        
        return render_template('project/detail.html', 
                             project=project,
                             material_file=material_file,
                             part_file=part_file,
                             labor_file=labor_file,
                             logistics_file=logistics_file,
                             material_files=material_files,
                             part_files=part_files,
                             labor_files=labor_files,
                             logistics_files=logistics_files,
                             latest_report=latest_report,
                             all_reports=all_reports)
    finally:
        db.close()


@project_bp.route('/<project_id>/export-report')
def export_cost_report(project_id):
    """导出成本报告（自动计算或使用已有报告）"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        project = db.query(Project).get(project_id)
        if not project:
            flash('项目不存在', 'error')
            return redirect(url_for('project.list_projects'))
        
        audit_log_service = AuditLogService(db)
        file_service = FileRecordService(db, audit_log_service)
        cost_service = CostCalculationService(db, audit_log_service)
        
        # 获取各类型文件的最新版本
        material_file = file_service.get_latest_valid_file(
            project_id=project_id,
            file_type=FileType.material_cost
        )
        part_file = file_service.get_latest_valid_file(
            project_id=project_id,
            file_type=FileType.part_cost
        )
        labor_file = file_service.get_latest_valid_file(
            project_id=project_id,
            file_type=FileType.labor_cost
        )
        logistics_file = file_service.get_latest_valid_file(
            project_id=project_id,
            file_type=FileType.logistics_cost
        )
        
        # 检查文件是否齐全
        missing_files = []
        if not material_file:
            missing_files.append('材料成本表')
        if not part_file:
            missing_files.append('配件成本表')
        if not labor_file:
            missing_files.append('人工成本表')
        if not logistics_file:
            missing_files.append('物流成本表')
        
        if missing_files:
            flash(f'缺少必需文件：{", ".join(missing_files)}，请先上传', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        # 检查文件状态
        files_to_check = [
            ('材料成本表', material_file),
            ('配件成本表', part_file),
            ('人工成本表', labor_file),
            ('物流成本表', logistics_file),
        ]
        
        invalid_files = []
        for file_name, file_record in files_to_check:
            if file_record.parse_status != ParseStatus.parsed:
                invalid_files.append(f'{file_name}（未解析）')
            elif file_record.validation_status not in (ValidationStatus.ok, ValidationStatus.confirmed):
                invalid_files.append(f'{file_name}（校验未通过）')
        
        if invalid_files:
            flash(f'以下文件状态不符合要求：{", ".join(invalid_files)}，请先完成解析和校验', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        # 尝试获取最新的成本报告
        latest_report = db.query(CostSummary).filter(
            CostSummary.project_id == project_id,
            CostSummary.status == CostSummaryStatus.ACTIVE
        ).order_by(desc(CostSummary.calculation_version)).first()
        
        # 如果没有报告，或者文件版本已更新，需要重新计算
        need_recalculate = False
        if not latest_report:
            need_recalculate = True
        else:
            # 检查文件版本是否匹配
            if (latest_report.material_file_id != material_file.id or
                latest_report.part_file_id != part_file.id or
                latest_report.labor_file_id != labor_file.id or
                latest_report.logistics_file_id != logistics_file.id):
                need_recalculate = True
        
        # 如果需要重新计算，先计算成本
        if need_recalculate:
            try:
                cost_summary = cost_service.generate_cost_summary(
                    project_id=project_id,
                    material_file_id=material_file.id,
                    part_file_id=part_file.id,
                    labor_file_id=labor_file.id,
                    logistics_file_id=logistics_file.id,
                    operator_id=session['user_id']
                )
                db.commit()
                latest_report = cost_summary
            except Exception as e:
                db.rollback()
                flash(f'成本计算失败: {str(e)}', 'error')
                return redirect(url_for('project.detail', project_id=project_id))
        
        # 生成报告DataFrame
        try:
            df = cost_service.generate_df_report(
                cost_summary=latest_report,
                operator_id=session.get('user_id', 'unknown')
            )
        except Exception as e:
            flash(f'生成报告失败: {str(e)}', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        # 生成 Excel
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='成本报告')
            
            output.seek(0)
            
            # 生成文件名
            filename = f"{project.raw_name}_成本报告_v{latest_report.calculation_version}.xlsx"
            # 清理文件名中的非法字符
            filename = filename.replace('/', '_').replace('\\', '_').replace(':', '_')
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            flash(f'生成Excel文件失败: {str(e)}', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
    finally:
        db.close()


@project_bp.route('/<project_id>/edit', methods=['POST'])
def update_project(project_id):
    """更新项目信息"""
    check = require_login()
    if check:
        return check
    
    business_code = request.form.get('business_code', '').strip() or None
    contract_code = request.form.get('contract_code', '').strip() or None
    spec_tags_str = request.form.get('spec_tags', '').strip()
    spec_tags = [tag.strip() for tag in spec_tags_str.split(',') if tag.strip()] if spec_tags_str else None
    
    db = get_session()
    try:
        audit_log_service = AuditLogService(db)
        name_normalization_service = NameNormalizationService(db, audit_log_service)
        project_service = ProjectService(db, audit_log_service, name_normalization_service)
        
        project = project_service.update_project(
            project_id=project_id,
            business_code=business_code,
            contract_code=contract_code,
            spec_tags=spec_tags,
            operator_id=session['user_id']
        )
        
        db.commit()
        flash('项目信息更新成功', 'success')
        return redirect(url_for('project.detail', project_id=project_id))
    except Exception as e:
        db.rollback()
        flash(f'更新失败: {str(e)}', 'error')
        return redirect(url_for('project.detail', project_id=project_id))
    finally:
        db.close()

