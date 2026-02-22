from typing import Optional, Dict
from decimal import Decimal
from uuid import uuid4
from datetime import datetime
import pandas as pd
from decimal import Decimal
from pandas import DataFrame
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.project import Project
from app.models.user import User
from app.models.file_record import FileRecord, ValidationStatus
from app.models.cost_summary import CostSummary
from app.models.material_item import MaterialItem
from app.models.part_item import PartItem
from app.models.labor_item import LaborItem
from app.models.logistics_item import LogisticsItem
from app.services.audit_log_service import AuditLogService
from app.db.enums import CostSummaryStatus, CostItemStatus
class CostCalculationService:
    """
    Generate immutable CostSummary snapshot and freeze source FileRecords.
    """

    def __init__(
        self,
        db: Session,
        audit_log_service: AuditLogService,
    ):
        self.db = db
        self.audit_log_service = audit_log_service
        
    def generate_cost_summary(
        self,
        *,
        project_id: str,
        material_file_id: str,
        part_file_id: str,
        labor_file_id: str,
        logistics_file_id: str,
        operator_id: str,
    ) -> CostSummary:
        """
        Generate a new CostSummary snapshot.
        :param project_id: Associated project ID
        :type project_id: str
        :param material_file_id: Material cost FileRecord ID
        :type material_file_id: str
        :param part_file_id: Part cost FileRecord ID
        :type part_file_id: str
        :param labor_file_id: Labor cost FileRecord ID  
        :type labor_file_id: str
        :param logistics_file_id: Logistics cost FileRecord ID (optional)
        :type logistics_file_id: Optional[str]
        :param operator_id: User ID of the operator performing the calculation
        """
        # =========
        # 0️⃣ 事务开始
        # =========

        # 1️⃣ 加载 FileRecords
        material_file = self._load_file(material_file_id)
        part_file = self._load_file(part_file_id)
        labor_file = self._load_file(labor_file_id)
        logistics_file = self._load_file(logistics_file_id)
            

        files = [material_file, part_file, labor_file, logistics_file]


        # 2️⃣ 校验 FileRecord 是否可用于核价
        for f in files:
            self._assert_file_usable_for_caculation(f, project_id)

        # 3️⃣ 汇总每个 FileRecord 的成本并计算项目直接成本
        material_cost = self._sum_items(MaterialItem, material_file.id)
        part_cost = self._sum_items(PartItem, part_file.id)
        labor_cost = self._sum_items(LaborItem, labor_file.id)
        logistics_cost = self._sum_items(LogisticsItem, logistics_file.id)
            

        total_cost = (
            material_cost + part_cost + labor_cost + logistics_cost
        )

        # 4️⃣ 计算新的 calculation_version
        new_version = self._next_calculation_version(project_id)

        # 5️⃣ 创建 CostSummary（不可变快照）
        summary = CostSummary(
            id=str(uuid4()),
            project_id=project_id,
            material_cost=material_cost,
            part_cost=part_cost,
            labor_cost=labor_cost,
            logistics_cost=logistics_cost,
            total_cost=total_cost,
            material_file_id=material_file.id,
            part_file_id=part_file.id,
            labor_file_id=labor_file.id,
            logistics_file_id=logistics_file.id,
            calculation_version=new_version,
            status=CostSummaryStatus.ACTIVE,
            calculated_at=datetime.now(),
            replaces_cost_summary_id=None,
            invalidated_at=None,
        )
        # 6️，旧 summary 作废（replaced）
        self._invalidate_old_summaries(project_id, summary.id)
        
        # 7️，锁定 FileRecords
        for f in files:
            f.locked = True
            
        #入库
        self.db.add(summary)
        self.db.flush()
        
        # 8️，写 AuditLog
        self.audit_log_service.record_create(
            project_id=project_id,
            entity_type="CostSummary",
            entity_id=summary.id,
            operator_id=operator_id,
        )

        return summary
    
    def _assert_file_usable_for_caculation(self, file: FileRecord, project_id: str) -> None:
        '''
        校验指定 FileRecord 是否可用于成本计算
        规则：
        - file must belong to the given project_id
        - parse_status must be 'parsed'
        - validation_status must be 'ok' or 'confirmed'
        - locked must be False
    
        :param file: FileRecord实例
        :type file: FileRecord
        :param project_id: 项目ID
        :type project_id: str
        '''
        if not file:
            raise ValueError("FileRecord not found")
        
        if file.project_id != project_id:
            raise ValueError("FileRecord does not belong to project")

        if file.parse_status != file.parse_status.parsed:
            raise ValueError("FileRecord not parsed")

        if file.validation_status not in (
            ValidationStatus.ok,
            ValidationStatus.confirmed
        ):  
            print(file.file_type, file.validation_status)
            raise ValueError("FileRecord not validated")

        if file.locked:
            raise ValueError("FileRecord already locked")
        
    def _assert_file_usable_for_report(self, file: FileRecord, project_id: str) -> None:
        '''
        校验指定 FileRecord 是否可用于成本计算
        规则：
        - file must belong to the given project_id
        - parse_status must be 'parsed'
        - validation_status must be 'ok' or 'confirmed'
    
        :param file: FileRecord实例
        :type file: FileRecord
        :param project_id: 项目ID
        :type project_id: str
        '''
        if not file:
            raise ValueError("FileRecord not found")
        
        if file.project_id != project_id:
            raise ValueError("FileRecord does not belong to project")

        if file.parse_status != file.parse_status.parsed:
            raise ValueError("FileRecord not parsed")

        if file.validation_status not in (
            ValidationStatus.ok,
            ValidationStatus.confirmed,
        ):  
            print(file.file_type, file.validation_status)
            raise ValueError("FileRecord not validated")
        
    def _sum_items(self, model, file_id: str) -> Decimal:
        '''
        聚合某一file下所有可计算的item的subtotal总和
        Rules:
        -only itemsfrom the given file_id are considered
        -only items where is_calculable is True are included
        -if no matching rows exist, return Decimal(0)
        
        return Decimal(rows or 0)
        return Decimal(rows or 0)
        :param model: Item模型类，如MaterialItem, PartItem等
        :type model: Type[MaterialItem | PartItem | LaborItem | LogisticsItem]
        :param file_id:  所属FileRecord ID
        :type file_id: str
        :return: filerecord下所有可计算的subtotal总和，file层面已经校验过了，因此item层面不需要再校验status
        :rtype: Decimal
        '''
        # Step 1: 查询数据库中，满足条件的 item 小计之和
        subtotal_sum = (
            self.db
            .query(func.sum(model.subtotal))
            .filter(
                model.source_file_id == file_id,
                model.is_calculable.is_(True),
            )
            .scalar()
        )

        # Step 2: 数据库在“没有任何行”时会返回 None，需要兜底为 0
        if subtotal_sum is None:
            return Decimal("0")

        # Step 3: 统一转成 Decimal，保证金额计算安全
        return Decimal(subtotal_sum)
    
    def _get_calculable_items(self, model, file_id: str) -> list:
        '''
        fetch all calculable items under a given file
        
        :param model: Item模型类，如MaterialItem, PartItem等
        :type model: Type[MaterialItem | PartItem | LaborItem | LogisticsItem]
        :param file_id: 所属FileRecord ID
        :type file_id: str
        '''
        return (
            self.db.query(model)
            .filter(
                model.source_file_id == file_id,
                model.is_calculable.is_(True),
            )
            .all()
        )

        
    def _next_calculation_version(self, project_id: str) -> int:
        '''
        计算下一个 calculation_version
        
        规则：
        - 从当前已有的最大 calculation_version + 1 得到
        - 如果当前没有任何 CostSummary，则返回 1
        :param project_id:  项目ID
        :type project_id: str
        :return: 下一个 calculation_version
        :rtype: int
        '''
        latest = (
            self.db.query(CostSummary)
            .filter(CostSummary.project_id == project_id)
            .order_by(CostSummary.calculation_version.desc())
            .first()
        )
        return 1 if not latest else latest.calculation_version + 1
    def get_latest_cost_summary(self,project_id: str) -> list[CostSummary]:
        '''
        获取某项目下最新的CostSummary记录列表
        :param project_id: 项目ID
        :type project_id: str
        :return: 最新的CostSummary记录列表
        :rtype: list[CostSummary]
        '''
        old_summaries = (
            self.db.query(CostSummary)
            .filter(
                CostSummary.project_id == project_id,
                CostSummary.status == CostSummaryStatus.ACTIVE,
            )
            .all()
        )
        return  old_summaries

    def _invalidate_old_summaries(self, project_id: str, new_id: str):
        
        old_summaries = self.get_latest_cost_summary(project_id)
        for old in old_summaries:
            if old.id == new_id:
                continue

            old.status = CostSummaryStatus.REPLACED
            old.invalidated_at = datetime.now()
            old.replaces_cost_summary_id = new_id

            self.audit_log_service.record_system_update(
                project_id=project_id,
                entity_type="CostSummary",
                entity_id=old.id,
                changed_attribute="status",
                before_value="active",
                after_value="replaced",
            )
    def _load_file(self, file_id: str) -> FileRecord:
        '''下载并返回指定ID的FileRecord实例，找不到则抛异常'''
        if not file_id:
            raise ValueError("file_id is required")

        file_record = self.db.query(FileRecord).get(file_id)
        if not file_record:
            raise ValueError(f"FileRecord not found: {file_id}")

        return file_record

    def generate_df_report(
        self,
        cost_summary: CostSummary,
        operator_id: str,
    ) -> pd.DataFrame:
        """
        Generate a human-readable cost report DataFrame
        based on an active CostSummary.

        This function does NOT persist data.
        """

        if cost_summary.status != CostSummaryStatus.ACTIVE:
            raise ValueError("Only active CostSummary is able to generate a report")
        # 1️，加载相关 project和FileRecords 
        project = self.db.query(Project).get(cost_summary.project_id)
        material_file = self._load_file(cost_summary.material_file_id)
        part_file = self._load_file(cost_summary.part_file_id)
        labor_file = self._load_file(cost_summary.labor_file_id)
        logistics_file = self._load_file(cost_summary.logistics_file_id)
        # 2，校验状态     
        if project is None:
            raise ValueError("Project not found")                        
        for f in [material_file, part_file, labor_file, logistics_file]:
            self._assert_file_usable_for_report(f, cost_summary.project_id)
        #置信级别工具
        def confidence_label(item_status: CostItemStatus) -> str:
            if item_status == CostItemStatus.ok:
                return "系统确认"
            if item_status == CostItemStatus.confirmed:
                return "人工确认"
            return ""
        #累加行构造DataFrame
        rows = []

        #项目信息
        rows.append(['产品直接生产成本统计'])
        rows.append(['产品编号',project.business_code])
        rows.append(["产品名称", project.normalized_name])
        rows.append(["产品标签", project.spec_tags])
        rows.append(["合同编号", project.contract_code])
        rows.append(["", ""])
        
        #材料明细
        rows.append(["一．材料（采购部填）"])
        rows.append(["名称", "规格型号", "数量", "单位", "材质", "参考重量", "单价", "小计", "置信级别"])
        #fetch all material items
        materials = (
            self.db.query(MaterialItem)
            .filter(MaterialItem.source_file_id == material_file.id,
                    MaterialItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed])
            )                           
            .all()
        )
        print('nunmber of materialitem loaded:',len(materials))
        #write material rows
        uploader = self.db.query(User).get(material_file.uploader_id)
        for m in materials:
            rows.append([
                m.normalized_name,
                m.spec,
                m.quantity,
                m.unit,
                m.material_grade,
                m.weight_kg,
                m.unit_price,
                m.subtotal,
                confidence_label(m.status),
            ])
        #write material summary row
        rows.append(["合计", "", "", "", "", "", "", cost_summary.material_cost, ""])
        rows.append([
            "表上传人", uploader.display_name if uploader is not None else "未知用户",
            "表名", material_file.original_name,
            "修改时间", material_file.updated_at,
            "版本", material_file.version,
        ])
        rows.append(["", ""])
        
        #配件明细
        rows.append(["二．配件（采购部填）"])
        rows.append(["名称", "规格型号", "数量", "单位", "", "", "单价", "小计", "置信级别"])
        #fetch all part items
        parts = (
            self.db.query(PartItem)
            .filter(PartItem.source_file_id == part_file.id,
                    PartItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed]),
            )
            .all()
        )
        print('nunmber of partitem loaded:',len(parts))
        #write part rows
        uploader = self.db.query(User).get(part_file.uploader_id)
        for p in parts:
            rows.append([
                p.normalized_name,
                p.spec,
                p.quantity,
                p.unit,
                "",
                "",
                p.unit_price,
                p.subtotal,
                confidence_label(p.status),
            ])
        #write part summary row
        rows.append(["合计", "", "", "", "", "", "", cost_summary.part_cost, ""])
        rows.append([
            "表上传人", uploader.display_name if uploader is not None else "未知用户",
            "表名", part_file.original_name,
            "修改时间", part_file.updated_at,
            "版本", part_file.version,
        ])
        rows.append(["", ""])
        #运费/安装费明细
        rows.append(["三．运费 / 安装费（采购部填）"])
        rows.append(["类型", "备注", "小计"])

        logistics = (
            self.db.query(LogisticsItem)
            .filter(LogisticsItem.source_file_id == logistics_file.id,
                    LogisticsItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed]),
                    LogisticsItem.is_calculable.is_(True)
            )
            .all()
        )
        print('nunmber of logisticsitem loaded:', len(logistics))
        
        uploader = self.db.query(User).get(logistics_file.uploader_id)
        for l in logistics:
            rows.append([l.type.value, l.description, l.subtotal])

        rows.append([
            "表上传人", uploader.display_name if uploader is not None else "未知用户",
            "表名", logistics_file.original_name,
            "修改时间", logistics_file.updated_at, 
            "版本", logistics_file.version,
        ])
        rows.append(["", ""])
        #人工明细
        rows.append(["四．加工费（生产部填）"])
        rows.append([
            "班组（外协单位）", "数量", "单位", "单价",
            "箱梁攻丝费、行走、液压站组装费、溜槽补助", "加工费", "吨位奖金", "小计", "置信级别"
        ])

        labors = (
            self.db.query(LaborItem)
            .filter(LaborItem.source_file_id == labor_file.id,
                    LaborItem.status.in_([CostItemStatus.ok, CostItemStatus.confirmed]),
            )
            .all()
        )
        print('nunmber of laboritem loaded:', len(labors))

        uploader = self.db.query(User).get(labor_file.uploader_id)
        for l in labors:
            processing_fee = (l.work_quantity or 0) * (l.unit_price or 0) if (l.unit == "吨") else (l.work_quantity or 0) * (l.unit_price or 0) * Decimal("0.001")
            ton_bonus = (l.work_quantity or 0) * 5 if (l.unit == "吨") else (l.work_quantity or 0) * Decimal("0.005")

            rows.append([
                l.normalized_group,
                l.work_quantity,
                l.unit,
                l.unit_price,
                l.extra_subsidies,
                processing_fee,
                ton_bonus,
                l.subtotal,
                confidence_label(l.status),
            ])

        rows.append(["合计", "", "", "", "", "", "", cost_summary.labor_cost, ""])
        rows.append([
            "表上传人", uploader.display_name if uploader is not None else "未知用户",
            "表名", labor_file.original_name,
            "修改时间", labor_file.updated_at,
            "版本", labor_file.version,
        ])
        #表位信息
        operator = self.db.query(User).get(operator_id)
        rows.append(["", ""])
        rows.append([
            "统计日期", datetime.now().strftime("%Y.%m.%d"),
            "统计人", operator.display_name if operator is not None else "未知用户",
            "直接生产成本", cost_summary.total_cost,
        ])
        #构造DataFrame返回
        df = pd.DataFrame(rows)
        return df


