from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.file_record import FileRecord
from app.models.material_item import MaterialItem
from app.models.part_item import PartItem
from app.models.labor_item import LaborItem
from app.models.logistics_item import LogisticsItem
from app.db.enums import CostItemStatus
from app.services.audit_log_service import AuditLogService
from app.services.validation_service import ValidationService
class ItemEditService:
    """
    Service for human correction of items and manual confirmation.

    Responsibilities:
    - Modify allowed fields on items
    - Record audit logs
    - Trigger re-validation
    - Perform warning -> confirmed transitions (human only)
    """
    def __init__(
        self,
        db: Session,
        audit_log_service: AuditLogService,
        validation_service: ValidationService,
    ):
        self.db = db
        self.audit_log_service = audit_log_service
        self.validation_service = validation_service
        
    def _load_item(self, item_type: str, item_id: str):
        model_map = {
            "material": MaterialItem,
            "part": PartItem,
            "labor": LaborItem,
            "logistics": LogisticsItem,
        }
        model = model_map.get(item_type)
        if not model:
            raise ValueError(f"Unknown item type: {item_type}")

        item = self.db.query(model).get(item_id)
        if not item:
            raise ValueError(f"{item_type} item not found: {item_id}")
        return item
    
    def _get_file_record(self, item) -> FileRecord:
        file_record = self.db.query(FileRecord).get(item.source_file_id)
        if not file_record:
            raise ValueError("Source FileRecord not found")
        return file_record
    
    def edit_item(
        self,
        *,
        item_type: str,
        item_id: str,
        updates: Dict[str, Any],
        operator_id: str,
    ):
        """
        Modify allowed fields of an item and trigger re-validation.
        :param item_type: Type of the item ,only allow four types:material, part, labor, logistics
        :param item_id: ID of the item to modify
        :param updates: Dictionary of field updates
        :param operator_id: User ID of the operator performing the edit
        """
        item = self._load_item(item_type, item_id)
        file_record = self._get_file_record(item)

        # 1️⃣ 文件是否被锁定
        if file_record.locked:
            raise RuntimeError("FileRecord is locked; item cannot be modified")

        # 2️⃣ 字段级修改（白名单）
        allowed_fields,validation_trigger_fields= self._allowed_edit_fields(item)
        need_validate = False#是否需要重新校验
        for field, new_value in updates.items():
            if field not in allowed_fields:
                raise ValueError(f"Field '{field}' is not editable")
            
            # 获取旧值，进行对比,如果没有变化则不触发校验，不赋值，不记录日志
            old_value = getattr(item, field)
            if old_value == new_value:
                continue
            
            if field in validation_trigger_fields:
                need_validate = True

            setattr(item, field, new_value)

            self.audit_log_service.record_update(
                project_id=item.project_id,
                entity_type=item.__class__.__name__,
                entity_id=item.id,
                changed_attribute=field,
                before_value=old_value,
                after_value=new_value,
                operator_id=operator_id,
            )

        # 3️⃣ 如果修改的属性是数值属性，则触发重新校验（只校验所属 FileRecord）
        if need_validate:
            self.validation_service.validate_file(file_record)
        #保存修改
        self.db.flush()
        
    def confirm_warning_item(
        self,
        *,
        item_type: str,
        item_id: str,
        operator_id: str,
    ):
        """
        Human confirmation for warning items.
        :param item_type: Type of the item,only allow four types:material, part, labor, logistics
        :param item_id: ID of the item to confirm
        :param operator_id: User ID of the operator performing the confirmation
        """
        item = self._load_item(item_type, item_id)
        file_record = self._get_file_record(item)
        # manual LogisticItem is not allowed to confirm
        from app.db.enums import FileType
        if item_type == "logistics" and file_record.file_type == FileType.manual:
            raise ValueError("Manual LogisticsItem cannot be confirmed")
        
        if file_record.locked:
            raise RuntimeError("FileRecord is locked; cannot confirm item")

        if item.status != CostItemStatus.warning:
            raise ValueError("Only warning items can be confirmed")

        old_status = item.status
        item.status = CostItemStatus.confirmed

        self.audit_log_service.record_update(
            project_id=item.project_id,
            entity_type=item.__class__.__name__,
            entity_id=item.id,
            changed_attribute="status",
            before_value=old_status.value,
            after_value=item.status.value,
            operator_id=operator_id,
        )

        # 确认后，重新聚合 FileRecord 状态
        self.validation_service.validate_file(file_record)
        
        #保存修改
        self.db.flush()

    def _allowed_edit_fields(self, item) -> tuple[set[str], set[str]]:
        '''
        获取指定item类型允许编辑的字段列表和触发校验的字段列表
        
        :param item: MaterialItem | PartItem | LaborItem | LogisticsItem
        :return: allowed_fields, validation_trigger_fields
        :rtype: tuple[set[str], set[str]]
        '''
        if isinstance(item, MaterialItem):
            return {
                "spec",
                "supplier",
                "quantity",
                "unit",
                "material_grade",
                "weight_kg",
                "unit_price",
                "subtotal"
            },{
                "quantity",
                "unit",
                "weight_kg",
                "unit_price",
                "subtotal"
            }
        if isinstance(item, PartItem):
            return {
                "spec",
                "supplier",
                "quantity",
                "unit",
                "unit_price",
                "subtotal",
            },{
                "quantity",
                "unit_price",
                "subtotal",
            }
        if isinstance(item, LaborItem):
            return {
                "work_quantity",
                "unit",
                "unit_price",
                "extra_subsidies",
                'ton_bonus',
                "subtotal",
            },{
                "work_quantity",
                "unit",
                "unit_price",
                "extra_subsidies",
                'ton_bonus',
                "subtotal",
            }   
        if isinstance(item, LogisticsItem):
            return {
                "description",
                "subtotal",
            },{
                "subtotal",
            }
        return set(),set()


