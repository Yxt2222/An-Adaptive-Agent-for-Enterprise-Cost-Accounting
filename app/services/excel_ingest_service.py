# app/services/excel_ingest_service.py
from typing import List, Type
import pandas as pd
from uuid import uuid4
from sqlalchemy.orm import Session
import math
import pandas as pd
from decimal import Decimal

import logging
logger = logging.getLogger(__name__)

from app.models.file_record import FileRecord, FileType, ParseStatus
from app.models.material_item import MaterialItem
from app.models.part_item import PartItem
from app.models.labor_item import LaborItem
from app.models.logistics_item import LogisticsItem
from app.db.enums import CostItemStatus, LogisticsType, NameDomain
from app.services.audit_log_service import AuditLogService
from app.services.name_normalization_service import NameNormalizationService
from app.services.file_record_service import FileRecordService

class ExcelIngestService:
    """
    Parse Excel file into cost items (Material / Part / Labor / Logistics).

    Responsibility:
    - Read Excel
    - Check column structure
    - Create Item records with raw data
    - Update FileRecord.parse_status
    """

    def __init__(
        self,
        db: Session,
        audit_log_service: AuditLogService,
        name_normalization_service: NameNormalizationService,
        file_service: FileRecordService,
    ):
        self.db = db
        self.audit_log_service = audit_log_service
        self.name_normalization_service = name_normalization_service
        self.file_service = file_service

    def ingest(self, file_record: FileRecord) -> None:
        """
        Parse Excel and generate corresponding items.
        Special rule (V0.1):
        - material_plan / part_plan are design/procurement plan evidence only:
        they do NOT generate items and do NOT participate in cost calculation.
        Parse only checks if the Excel can be opened successfully.
  
        Raises:
            ValueError: if file cannot be parsed
        file_record: FileRecord
        FileRecord.file_type:"material_plan","part_plan","material_cost","part_cost","labor_cost","logistics_cost","manual"

        """
        # manual LogisticFileRecord is not allowed to be parsed:
        if file_record.file_type == FileType.manual:
            raise ValueError("Manual FileRecord cannot be parsed")
        
        old_status = file_record.parse_status

        try:
            # 1) Always try opening the excel first (parse = "can open")
            _ = self._load_excel(file_record)

            # 2) Plan files: only store FileRecord, no items
            if file_record.file_type in {FileType.material_plan, FileType.part_plan}:
                file_record.parse_status = ParseStatus.parsed

                self.audit_log_service.record_system_update(
                    project_id=file_record.project_id,
                    entity_type="FileRecord",
                    entity_id=file_record.id,
                    changed_attribute="parse_status",
                    before_value=old_status.value if old_status else None,
                    after_value=file_record.parse_status.value if file_record.parse_status else None,
                )
                return  # ✅ stop here, no items generated

            # 3) Cost-related files: must check columns + create items
            df = self._load_excel(file_record)  # (you may reuse cached df if you want)
            self._check_columns(file_record.file_type, df)

            #解析material_cost
            if file_record.file_type == FileType.material_cost:
                self._parse_material_items(file_record, df)
            #解析part_cost
            elif file_record.file_type == FileType.part_cost:
                self._parse_part_items(file_record, df)
            #解析labor_cost
            elif file_record.file_type == FileType.labor_cost:
                self._parse_labor_items(file_record, df)
            #解析logistics_cost
            elif file_record.file_type == FileType.logistics_cost:
                self._parse_logistics_items(file_record, df)

            else:
                raise ValueError(f"Unsupported file_type: {file_record.file_type}")

            file_record.parse_status = ParseStatus.parsed

            self.audit_log_service.record_system_update(
                project_id=file_record.project_id,
                entity_type="FileRecord",
                entity_id=file_record.id,
                changed_attribute="parse_status",
                before_value=old_status.value if old_status else None,
                after_value=file_record.parse_status.value if old_status else None,
            )

        except Exception:
            file_record.parse_status = ParseStatus.failed

            self.audit_log_service.record_system_update(
                project_id=file_record.project_id,
                entity_type="FileRecord",
                entity_id=file_record.id,
                changed_attribute="parse_status",
                before_value=old_status.value if old_status else None,
                after_value=file_record.parse_status.value if old_status else None,
            )
            raise           
    def _load_excel(self, file_record: FileRecord) -> pd.DataFrame:
        """
        Load Excel file into DataFrame.
        """
        try:
            return pd.read_excel(file_record.storage_path)
        except Exception as e:
            raise ValueError(f"Failed to read Excel: {e}")
    def _check_columns(self, file_type: FileType, df: pd.DataFrame) -> None:
        required_columns_map = {
            FileType.material_plan: [
                "名称", "规格型号", "数量", "单位", "材质", "参考重量\n（kg）", "单价", "小计"
            ],
            FileType.part_plan: [
                "名称", "规格型号", "数量", "单位", "单价", "小计"
            ],
            FileType.labor_cost: [
                "班组（外协单位）", "数量", "单位", "单价", "加工费", "吨位奖金", "箱梁攻丝费、行走、液压站组装费、溜槽补助", "小计"
            ],
            FileType.logistics_cost: [
                "类型", "备注", "小计"
            ],
        }

        required = required_columns_map.get(file_type, [])
        missing = [c for c in required if c not in df.columns]

        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
    def _parse_material_items(self, file_record: FileRecord, df: pd.DataFrame) -> None:
        '''
        解析材料成本Excel，生成MaterialItem记录
        
        :param file_record: file_record
        :type file_record: FileRecord
        :param df: file内容的DataFrame表示
        :type df: pd.DataFrame
        '''
        items: List[MaterialItem] = []
        curname = ''
        curunit = ''
        curmaterial_grade = ''
        for _, row in df.iterrows():
            rawname = row.get("名称") if pd.notna(row.get("名称")) else curname
            normalizedname = self.name_normalization_service.normalize( domain = NameDomain.MATERIAL,raw_name=str(rawname).strip())
            item = MaterialItem(
                id =  str(uuid4()),
                project_id=file_record.project_id,
                source_file_id=file_record.id,
                raw_name=rawname,
                normalized_name=normalizedname,
                spec=row.get("规格型号"),
                quantity=row.get("数量"),
                unit=row.get("单位") if pd.notna(row.get("单位")) else curunit,
                material_grade=row.get("材质") if pd.notna(row.get("材质")) else curmaterial_grade,
                weight_kg=row.get("参考重量\n（kg）"),
                unit_price=row.get("单价"),
                subtotal=row.get("小计"),
                status=CostItemStatus.warning,  # 保守初始态
                is_calculable=True,
            )
            items.append(item)
            curname = row.get("名称") if pd.notna(row.get("名称")) else curname
            curunit = row.get("单位") if pd.notna(row.get("单位")) else curunit
            curmaterial_grade = row.get("材质") if pd.notna(row.get("材质")) else curmaterial_grade
            
        logger.info(f"[material] df rows={len(df)} parsed={len(items)} file_id={file_record.id}")
        self.db.add_all(items)
        self.db.flush()
        logger.info("[material] flushed")
        
    def _parse_part_items(self, file_record: FileRecord, df: pd.DataFrame) -> None:
        """
        解析配件成本 Excel，生成 PartItem，并自动生成 bundle_key
        """
        def switch_status(status, idx):
            if status is None:
                status = idx
            else:
                status = None
            return status
        
        def has_value(x):
            return x is not None and not (isinstance(x, float) and math.isnan(x))
        
        rows = df.reset_index(drop=True)
        items: List[PartItem] = []

        bundle_idx = 1
        if len(rows) == 0:
            return
        elif len(rows) == 1:
            cur_status = None
        else:
            cur_status = None if has_value(rows.iloc[1].get("单价")) else bundle_idx# 如果第二行单价有值，说明第一行不是bundle，cur_status从None开始；否则是bundle，从1开始
        
        cur_name = ''
        for i in range(len(rows)):
            row = rows.iloc[i]

            # ---------- 判断合并关系 ----------
            cur_has = has_value(row.get("单价"))

            prev_has = has_value(rows.iloc[i - 1].get("单价")) if i > 0 else True
            next_has = has_value(rows.iloc[i + 1].get("单价")) if i < len(rows) - 1 else True

            # 是否与前一行合并 / 后一行合并
            #merged_with_prev = not cur_has and prev_has
            #merged_with_next = cur_has and not next_has

            
            '''
            默认先变状态，在生成item
            前中后分八种情况：
            非空,非空，非空： 都非bundle,无逻辑
            非空,非空，空： 从非bundle变为bundle，变状态，开始了一个新的bundle,id+1
            非空，空，非空： 和前行同属一个Bundle，不变状态
            空，非空，非空： 从bundle变为非bundle，变状态
            空，空，非空： 和前行都属一个bundle，不变状态
            空，非空，空： 从bundle变为bundle，不变状态，但，开始新的bundle,id+1
            非空，空，空： 和前行都属一个bundle，不变状态
            空，空，空： 都属一个bundle，不变状态
            '''
            #状态变化
    
            #非空，非空，空
            if prev_has and cur_has and not next_has:
                cur_status = switch_status(cur_status,bundle_idx)
                bundle_idx += 1
            #空，非空，非空
            if not prev_has and cur_has and next_has:
                cur_status = switch_status(cur_status,bundle_idx)
            #空，非空，空
            if not prev_has and cur_has and not next_has:
                #更新cur_status的值
                if cur_status is not None:
                    cur_status = bundle_idx
                bundle_idx += 1
                
           
            # ---------- 生成 item ----------
            rawname = row.get("名称") if pd.notna(row.get("名称")) else cur_name
            normalizedname = self.name_normalization_service.normalize( domain = NameDomain.PART,raw_name=str(rawname).strip())
            item = PartItem(
                id=str(uuid4()),
                project_id=file_record.project_id,
                source_file_id=file_record.id,
                raw_name=rawname,
                normalized_name=normalizedname,
                spec=row.get("规格型号"),
                quantity=row.get("数量"),
                unit=row.get("单位"),
                unit_price=row.get("单价"),
                subtotal=row.get("小计") if pd.notna(row.get("小计")) else 0.0,
                bundle_key=cur_status,   
                status=CostItemStatus.warning,
                is_calculable=True,
            )
            cur_name = item.raw_name if pd.notna(row.get("名称")) else cur_name

            items.append(item)

        self.db.add_all(items)
        self.db.flush()

    def _parse_labor_items(self, file_record: FileRecord, df: pd.DataFrame) -> None:
        '''
        解析劳务成本Excel，生成LaborItem记录
        
        :param file_record: file_record
        :type file_record: FileRecord
        :param df:  file内容的DataFrame表示
        :type df: pd.DataFrame
        '''
        items: List[LaborItem] = []
        cur_name = ''
        for _, row in df.iterrows():
            rawname = row.get("班组（外协单位）") if pd.notna(row.get("班组（外协单位）")) else cur_name
            normalizedname = self.name_normalization_service.normalize(domain = NameDomain.LABOR_GROUP,raw_name=str(rawname).strip())
            item = LaborItem(
                id= str(uuid4()),
                project_id=file_record.project_id,
                source_file_id=file_record.id,
                raw_group=rawname,
                normalized_group=normalizedname,
                work_quantity=row.get("数量"),
                unit=row.get("单位"),
                unit_price=row.get("单价"),
                ton_bonus=row.get("吨位奖金"),
                extra_subsidies=row.get("箱梁攻丝费、行走、液压站组装费、溜槽补助"),
                subtotal=row.get("小计"),
                status=CostItemStatus.warning,
                is_calculable=True,
            )
            items.append(item)
            cur_name = row.get("班组（外协单位）") if pd.notna(row.get("班组（外协单位）")) else cur_name
        self.db.add_all(items)
        self.db.flush()
        
    def _parse_logistics_items(self, file_record: FileRecord, df: pd.DataFrame) -> None:
        '''
        解析物流成本Excel，生成LogisticsItem记录
        
        :param file_record: file_record
        :type file_record: FileRecord
        :param df: file内容的DataFrame表示
        :type df: pd.DataFrame
        '''
        def get_type(raw_type) -> LogisticsType:
            if not raw_type:
                return LogisticsType.OTHER

            t = str(raw_type).strip()

            if t == "运输":
                return LogisticsType.TRANSPORT
            elif t == "安装":
                return LogisticsType.INSTALLATION
            else:
                return LogisticsType.OTHER

        if file_record == FileType.manual:
            raise ValueError("Manual FileRecord cannot be parsed")
        items: List[LogisticsItem] = []
        
        for _, row in df.iterrows():
            item = LogisticsItem(
                id= str(uuid4()),
                project_id=file_record.project_id,
                source_file_id=file_record.id,
                type=get_type(str(row.get("类型"))),
                description=row.get("备注"),
                subtotal=row.get("小计"),
                status=CostItemStatus.warning,
                is_calculable=True,
            )
            items.append(item)

        self.db.add_all(items)
        self.db.flush()


    def parse_manual_logistics_item(self,
                                    project_id:str,
                                    type:str,
                                    description:str,
                                    subtotal:float,
                                    operator_id:str) -> tuple[FileRecord, LogisticsItem]:
        '''
        user手动添加LogisticsItem记录：
        规则：用户输入相关数据->生成manual FileRecord ->生成LogisticsItem记录 ->入库
        
        :param project_id: 项目ID
        :type project_id: str
        :param description: 备注描述
        :type description: str
        :param subtotal: 小计金额
        :type subtotal: float
        :param operator_id: 操作用户ID
        :type operator_id: str
        '''
        def get_type(raw_type) -> LogisticsType:
            if not raw_type:
                return LogisticsType.OTHER

            t = str(raw_type).strip()

            if t == "运输":
                return LogisticsType.TRANSPORT
            elif t == "安装":
                return LogisticsType.INSTALLATION
            else:
                return LogisticsType.OTHER
        #file record是入库了的
        logistics_file = self.file_service.create_update_file_record(
            project_id=project_id,
            file_type=FileType.manual,
            operator_id=operator_id
        )
        logistics_item = LogisticsItem(
                id=str(uuid4()),    
                project_id=project_id,
                source_file_id=logistics_file.id,
                type= get_type(str(type)),
                description=description,
                subtotal=subtotal,
            )
        self.db.add(logistics_item)

        
        return logistics_file,logistics_item

    def parse_manual_material_item(
        self,
        project_id: str,
        raw_name: str,
        operator_id: str,
        spec: str = None,
        quantity: float = None,
        unit: str = None,
        material_grade: str = None,
        weight_kg: float = None,
        unit_price: float = None,
        subtotal: float = None,
        supplier: str = None,
    ) -> tuple[FileRecord, MaterialItem]:
        '''
        用户手动添加MaterialItem记录
        '''
        from app.db.enums import CostItemStatus
        
        material_file = self.file_service.create_update_file_record(
            project_id=project_id,
            file_type=FileType.manual,
            operator_id=operator_id
        )
        
        material_item = MaterialItem(
            id=str(uuid4()),
            project_id=project_id,
            source_file_id=material_file.id,
            raw_name=raw_name,
            normalized_name=raw_name,  # 初始时与raw_name相同，后续可通过名称规范化服务更新
            spec=spec,
            quantity=Decimal(str(quantity)) if quantity is not None else None,
            unit=unit,
            material_grade=material_grade,
            weight_kg=Decimal(str(weight_kg)) if weight_kg is not None else None,
            unit_price=Decimal(str(unit_price)) if unit_price is not None else None,
            subtotal=Decimal(str(subtotal)) if subtotal is not None else None,
            supplier=supplier,
            status=CostItemStatus.ok,  # 手工输入默认为ok状态
        )
        self.db.add(material_item)

        
        return material_file, material_item

    def parse_manual_part_item(
        self,
        project_id: str,
        raw_name: str,
        operator_id: str,
        spec: str = None,
        quantity: float = None,
        unit: str = None,
        unit_price: float = None,
        subtotal: float = None,
        supplier: str = None,
    ) -> tuple[FileRecord, PartItem]:
        '''
        用户手动添加PartItem记录
        '''
        from app.db.enums import CostItemStatus
        
        part_file = self.file_service.create_update_file_record(
            project_id=project_id,
            file_type=FileType.manual,
            operator_id=operator_id
        )
        
        part_item = PartItem(
            id=str(uuid4()),
            project_id=project_id,
            source_file_id=part_file.id,
            raw_name=raw_name,
            normalized_name=raw_name,
            spec=spec,
            quantity=Decimal(str(quantity)) if quantity is not None else None,
            unit=unit,
            unit_price=Decimal(str(unit_price)) if unit_price is not None else None,
            subtotal=Decimal(str(subtotal)) if subtotal is not None else None,
            supplier=supplier,
            status=CostItemStatus.ok,
        )
        self.db.add(part_item)

        return part_file, part_item

    def parse_manual_labor_item(
        self,
        project_id: str,
        raw_group: str,
        operator_id: str,
        work_quantity: float = None,
        unit: str = None,
        unit_price: float = None,
        extra_subsidies: float = None,
        ton_bonus: float = None,
        subtotal: float = None,
    ) -> tuple[FileRecord, LaborItem]:
        '''
        用户手动添加LaborItem记录
        '''
        from app.db.enums import CostItemStatus
        
        labor_file = self.file_service.create_update_file_record(
            project_id=project_id,
            file_type=FileType.manual,
            operator_id=operator_id
        )
        
        labor_item = LaborItem(
            id=str(uuid4()),
            project_id=project_id,
            source_file_id=labor_file.id,
            raw_group=raw_group,
            normalized_group=raw_group,
            work_quantity=Decimal(str(work_quantity)) if work_quantity is not None else None,
            unit=unit,
            unit_price=Decimal(str(unit_price)) if unit_price is not None else None,
            extra_subsidies=Decimal(str(extra_subsidies)) if extra_subsidies is not None else None,
            ton_bonus=Decimal(str(ton_bonus)) if ton_bonus is not None else None,
            subtotal=Decimal(str(subtotal)) if subtotal is not None else None,
            status=CostItemStatus.ok,
        )
        self.db.add(labor_item)
        
        return labor_file, labor_item


