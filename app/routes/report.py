# app/routes/report.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from app.db.session import get_session
from app.services.cost_calculation_service import CostCalculationService
from app.services.audit_log_service import AuditLogService
from app.models.cost_summary import CostSummary
from app.models.project import Project
from app.models.file_record import FileRecord
from app.models.material_item import MaterialItem
from app.models.part_item import PartItem
from app.models.labor_item import LaborItem
from app.models.logistics_item import LogisticsItem
from app.db.enums import CostSummaryStatus, CostItemStatus, FileType
from sqlalchemy import desc
import pandas as pd
import io

report_bp = Blueprint('report', __name__, url_prefix='/projects/<project_id>/reports')


def require_login():
    """检查登录状态"""
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('auth.login'))
    return None


@report_bp.route('/calculate', methods=['GET', 'POST'])
def calculate_cost(project_id):
    """成本计算页面"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        project = db.query(Project).get(project_id)
        if not project:
            flash('项目不存在', 'error')
            return redirect(url_for('project.list_projects'))
        
        if request.method == 'POST':
            material_file_id = request.form.get('material_file_id')
            part_file_id = request.form.get('part_file_id')
            labor_file_id = request.form.get('labor_file_id')
            logistics_file_id = request.form.get('logistics_file_id')
            
            if not all([material_file_id, part_file_id, labor_file_id, logistics_file_id]):
                flash('请选择所有必需的文件版本', 'error')
                return redirect(url_for('report.calculate_cost', project_id=project_id))
            
            try:
                audit_log_service = AuditLogService(db)
                cost_service = CostCalculationService(db, audit_log_service)
                
                cost_summary = cost_service.generate_cost_summary(
                    project_id=project_id,
                    material_file_id=material_file_id,
                    part_file_id=part_file_id,
                    labor_file_id=labor_file_id,
                    logistics_file_id=logistics_file_id,
                    operator_id=session['user_id']
                )
                
                db.commit()
                flash('成本计算成功', 'success')
                return redirect(url_for('report.view_report', project_id=project_id, report_id=cost_summary.id))
            except Exception as e:
                db.rollback()
                flash(f'计算失败: {str(e)}', 'error')
                return redirect(url_for('report.calculate_cost', project_id=project_id))
        
        # GET 请求：显示计算页面
        from app.services.file_record_service import FileRecordService
        audit_log_service = AuditLogService(db)
        file_service = FileRecordService(db, audit_log_service)
        
        # 获取各类型文件的所有可用版本
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
        
        return render_template('report/calculate.html',
                             project=project,
                             material_files=material_files,
                             part_files=part_files,
                             labor_files=labor_files,
                             logistics_files=logistics_files)
    finally:
        db.close()


@report_bp.route('/<report_id>')
def view_report(project_id, report_id):
    """查看成本报告"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        cost_summary = db.query(CostSummary).get(report_id)
        if not cost_summary or cost_summary.project_id != project_id:
            flash('报告不存在', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        project = db.query(Project).get(project_id)
        
        # 获取文件信息
        material_file = db.query(FileRecord).get(cost_summary.material_file_id)
        part_file = db.query(FileRecord).get(cost_summary.part_file_id)
        labor_file = db.query(FileRecord).get(cost_summary.labor_file_id)
        logistics_file = db.query(FileRecord).get(cost_summary.logistics_file_id)
        
        # 获取明细数据
        materials = db.query(MaterialItem).filter(
            MaterialItem.source_file_id == cost_summary.material_file_id,
            MaterialItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed])
        ).all()
        
        parts = db.query(PartItem).filter(
            PartItem.source_file_id == cost_summary.part_file_id,
            PartItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed])
        ).all()
        
        labors = db.query(LaborItem).filter(
            LaborItem.source_file_id == cost_summary.labor_file_id,
            LaborItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed])
        ).all()
        
        logistics = db.query(LogisticsItem).filter(
            LogisticsItem.source_file_id == cost_summary.logistics_file_id,
            LogisticsItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed]),
            LogisticsItem.is_calculable.is_(True)
        ).all()
        
        return render_template('report/view.html',
                             project=project,
                             cost_summary=cost_summary,
                             material_file=material_file,
                             part_file=part_file,
                             labor_file=labor_file,
                             logistics_file=logistics_file,
                             materials=materials,
                             parts=parts,
                             labors=labors,
                             logistics=logistics)
    finally:
        db.close()


@report_bp.route('/<report_id>/download/excel')
def download_excel(project_id, report_id):
    """下载 Excel 格式报告"""
    check = require_login()
    if check:
        return check
    
    db = get_session()
    try:
        cost_summary = db.query(CostSummary).get(report_id)
        if not cost_summary or cost_summary.project_id != project_id:
            flash('报告不存在', 'error')
            return redirect(url_for('project.detail', project_id=project_id))
        
        audit_log_service = AuditLogService(db)
        cost_service = CostCalculationService(db, audit_log_service)
        
        df = cost_service.generate_df_report(
            cost_summary=cost_summary,
            operator_id=session.get('user_id', 'unknown')
        )
        
        # 生成 Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='成本报告')
        
        output.seek(0)
        
        project = db.query(Project).get(project_id)
        filename = f"{project.raw_name}_成本报告_v{cost_summary.calculation_version}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    finally:
        db.close()

