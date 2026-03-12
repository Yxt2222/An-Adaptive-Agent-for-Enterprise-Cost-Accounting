# app/services/cost_report_service.py

from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from sqlalchemy.orm import Session
from app.models.cost_summary import CostSummary
from app.db.enums import CostSummaryStatus
from app.services.audit_log_service import AuditLogService
from app.services.cost_calculation_service import CostCalculationService

# ===============================
# 常量配置
# ===============================
REPORT_OUTPUT_DIR = Path("uploads") / "generated_reports"
REPORT_FILE_PREFIX = "cost_summary_report"
REPORT_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CostReportService:
    """
    负责成本报告的生成、存储、命名和CostSummary字段更新
    """

    def __init__(
        self,
        db: Session,
        audit_log_service: AuditLogService,
        cost_calculation_service: CostCalculationService,
    ):
        self.db = db
        self.audit_log_service = audit_log_service
        self.cost_calculation_service = cost_calculation_service

    def generate_report(
        self,
        cost_summary_id: str,
        operator_id: str,
    ) -> Dict[str, Any]:
        """
        职责：
        生成成本报告Excel文件
        文件路径管理
        文件命名
        Excel导出
        CostSummary更新
        审计日志记录
        Returns:
            包含报告元数据的字典：
            - cost_summary_id
            - project_id
            - calculation_version
            - file_name
            - storage_path
            - mime_type
            - generated_at
            - download_url
        """
        # 1️⃣ 校验CostSummary是否存在且为ACTIVE状态
        cost_summary = self.db.query(CostSummary).get(cost_summary_id)
        
        if not isinstance(cost_summary, CostSummary) or not cost_summary:
            raise ValueError(f"CostSummary with id {cost_summary_id} not found.")
        
        if cost_summary.status != CostSummaryStatus.ACTIVE:
            raise ValueError("Only active CostSummary is able to generate a report.")

        # 2️⃣ 调用CostCalculationService生成DataFrame
        df_report = self.cost_calculation_service.generate_df_report(
            cost_summary=cost_summary,
            operator_id=operator_id,
        )

        # 3️⃣ 确保输出目录存在
        REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 4️⃣ 生成文件名
        file_name = self._build_report_file_name(cost_summary)

        # 5️⃣ 生成完整路径（确保唯一性）
        output_path = (REPORT_OUTPUT_DIR / file_name).resolve()
        
        # 如果文件已存在，添加序号
        counter = 1
        while output_path.exists():
            name_without_ext = file_name.rsplit('.', 1)[0]#右边按.分割1次，然后取分割后的第1部分即去掉扩展名，得到去掉扩展名后的文件名
            ext = file_name.rsplit('.', 1)[1]#取扩展名
            file_name = f"{name_without_ext}_{counter}.{ext}"
            output_path = (REPORT_OUTPUT_DIR / file_name).resolve()
            counter += 1

        # 6️⃣ 导出Excel文件
        df_report.to_excel(output_path, index=False, header=False)

        # 7️⃣ 更新CostSummary的报告字段
        self._update_cost_summary_report_fields(
            cost_summary=cost_summary,
            file_name=file_name,
            storage_path=str(output_path),
        )

        # 8️⃣ 记录审计日志
        self.audit_log_service.record_update(
            project_id=cost_summary.project_id,
            entity_type="CostSummary",
            entity_id=cost_summary.id,
            changed_attribute="report_generated",
            before_value=None,
            after_value=file_name,
            operator_id=operator_id,
        )

        # 9️⃣ 返回报告元数据
        return {
            "cost_summary_id": cost_summary.id,
            "project_id": cost_summary.project_id,
            "calculation_version": cost_summary.calculation_version,
            "file_name": file_name,
            "storage_path": str(output_path),
            "mime_type": REPORT_MIME_TYPE,
            "generated_at": datetime.now().isoformat(),
            "download_url": f"/api/cost-reports/{cost_summary.id}/download",
        }

    def _build_report_file_name(self, cost_summary: CostSummary) -> str:
        """
        构建报告文件名
        
        格式: cost_summary_report_v{version}_{id前8位}_{timestamp}.xlsx
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        id_prefix = cost_summary.id[:8] if cost_summary.id else "unknown"
        return f"{REPORT_FILE_PREFIX}_v{cost_summary.calculation_version}_{id_prefix}_{timestamp}.xlsx"

    def _update_cost_summary_report_fields(
        self,
        cost_summary: CostSummary,
        file_name: str,
        storage_path: str,
    ) -> None:
        """
        更新CostSummary的报告相关字段
        """
        cost_summary.report_file_name = file_name
        cost_summary.report_storage_path = storage_path
        cost_summary.report_generated_at = datetime.now()
        
        self.db.flush()
