from typing import Dict, Any, List
from sqlalchemy.orm import Session
 
from app.models.file_record import FileRecord
from app.models.material_item import MaterialItem
from app.models.part_item import PartItem
from app.models.labor_item import LaborItem
from app.models.logistics_item import LogisticsItem
from app.db.enums import CostItemStatus,FileType
from app.services.audit_log_service import AuditLogService
from app.services.validation_service import ValidationReport, ValidationService
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
        
    def _load_item(self, item_type: str, item_id: str) -> MaterialItem | PartItem | LaborItem | LogisticsItem:
        model_map = {
            "material": MaterialItem,
            "part": PartItem,
            "labor": LaborItem,
            "logistics": LogisticsItem,
        }
        model = model_map.get(item_type)
        if not model:
            raise ValueError(f"Unknown item type: {item_type}")

        item = self.db.get(model, item_id)
        if not item:
            raise ValueError(f"{item_type} item not found: {item_id}")
        return item
    
    def _get_file_record(self, item: MaterialItem | PartItem | LaborItem | LogisticsItem) -> FileRecord:
        if not isinstance(item, (MaterialItem, PartItem, LaborItem, LogisticsItem)):
            raise ValueError("Invalid item type for file record retrieval")
        file_record = self.db.get(FileRecord, item.source_file_id)
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
        auto_validate: bool = True,
    ) -> bool:
        """
        Modify allowed fields of an item and trigger re-validation.
        :param item_type: Type of the item ,only allow four types:material, part, labor, logistics
        :param item_id: ID of the item to modify
        :param updates: Dictionary of field updates
        :param operator_id: User ID of the operator performing the edit
        return: whether validation is needed (for batch aggregation use)
        """
        item = self._load_item(item_type, item_id)
        file_record = self._get_file_record(item)

        # 1️ 文件是否被锁定
        if file_record.locked:
            raise RuntimeError("FileRecord is locked; item cannot be modified")

        # 2️ 字段级修改（白名单）
        allowed_fields,validation_trigger_fields= self._allowed_edit_fields(item)
        
        need_validate = False#是否有任何修改，是否需要重新校验

        for field, new_value in updates.items():
            if field not in allowed_fields:
                raise RuntimeError(f"Field '{field}' not in allowed list.It's not editable")
                
            # 获取旧值，进行对比,如果没有变化则不触发校验，不赋值，不记录日志
            old_value = getattr(item, field)
            if old_value == new_value:
                continue
            if field in validation_trigger_fields:
                need_validate = True
            #赋新值
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
        #保存修改
        self.db.flush() 
        
        if auto_validate and need_validate:
            self.validation_service.validate_file(file_record)
            self.db.flush()
        return need_validate
  
           
    def batch_edit_items(self,
                         item_type_lst:List[str],
                         item_id_lst:List[str],
                         updates_lst:List[Dict[str, Any]],
                         operator_id:str) -> None | ValidationReport:
        """
        Batch edit items. All items must belong to the same source file. Validation is triggered after all edits are done.
        :param item_type_lst: List of item types, only allow four types:material,part, labor, logistics
        :param item_id_lst: List of item IDs to modify
        :param updates_lst: List of dictionaries of field updates, corresponding to each item
        :param operator_id: User ID of the operator performing the edit
        """
        changeset_size = len(item_type_lst)
        if not (len(item_id_lst) == changeset_size and len(updates_lst) == changeset_size):
            raise ValueError("Length of item_type_lst, item_id_lst and updates_lst must be the same")
        if changeset_size == 0:
            raise ValueError("Empty batch is not allowed")
        
        source_file_id = None
        need_validate_any = False
        for i in range(changeset_size):
            item = self._load_item(item_type_lst[i], item_id_lst[i])
            if not item.source_file_id:
                raise ValueError(f"Item {item_type_lst[i]} {item_id_lst[i]} does not have a source_file_id")
            if source_file_id is None:
                source_file_id = item.source_file_id
            elif item.source_file_id != source_file_id:
                raise ValueError("All items in the batch must belong to the same source file")
            need_validate_any = need_validate_any or self.edit_item(
                item_type=item_type_lst[i],
                item_id=item_id_lst[i],
                updates=updates_lst[i],
                operator_id=operator_id,
                auto_validate=False, #批量修改时，等所有修改完成后再统一触发校验
            )
        if not source_file_id:
            raise ValueError("Failed to determine source_file_id from items")
        
        #所有修改完成后，触发校验
        if need_validate_any:
            file_record = self.db.get(FileRecord, source_file_id)
            if not file_record:
                raise ValueError("Failed to retrieve Source file")
            validation_report = self.validation_service.validate_file(file_record)
            self.db.flush()
            return validation_report
        else:
            return None
        
    def confirm_warning_item(
        self,
        *,
        item_type: str,
        item_id: str,
        operator_id: str,
        auto_validate: bool = True,
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
 
        if item_type == "logistics" and file_record.file_type == FileType.manual:
            raise RuntimeWarning("Manual LogisticsItem cannot be confirmed")
        
        if file_record.locked:
            raise RuntimeError("FileRecord is locked; cannot confirm item")

        if item.status != CostItemStatus.warning:
            raise RuntimeWarning("Only warning items can be confirmed")
         
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
        self.db.flush()

        # 确认后，重新聚合 FileRecord 状态
        if auto_validate:
            self.validation_service.validate_file(file_record)
            #保存修改
            self.db.flush()
        
    def batch_confirm_items(self,
                         item_type_lst:List[str],
                         item_id_lst:List[str],
                         operator_id:str) -> ValidationReport:
        """
        Batch confirm items. All items must belong to the same source file. Validation is triggered after all confirmations are done.
        :param item_type_lst: List of item types, only allow four types:material,part, labor, logistics
        :param item_id_lst: List of item IDs to modify
        :param operator_id: User ID of the operator performing the edit
        """
        changeset_size = len(item_type_lst)
        if not (len(item_id_lst) == changeset_size):
            raise ValueError("Length of item_type_lst and item_id_lst must be the same")
        if changeset_size == 0:
            raise ValueError("Empty batch is not allowed")
        
        source_file_id = None
        for i in range(changeset_size):
            item = self._load_item(item_type_lst[i], item_id_lst[i])
            if not item.source_file_id:
                raise ValueError(f"Item {item_type_lst[i]} {item_id_lst[i]} does not have a source_file_id")
            #保存source_file_id
            if source_file_id is None:
                source_file_id = item.source_file_id
            #确保批量操作的items属于同一个文件 
            elif item.source_file_id != source_file_id:
                raise ValueError("All items in the batch must belong to the same source file")
            self.confirm_warning_item(
                item_type=item_type_lst[i],
                item_id=item_id_lst[i],
                operator_id=operator_id,
                auto_validate=False, #批量确认时，等所有确认完成后再统一触发校验
            )
        if not source_file_id:
            raise ValueError("Failed to determine source_file_id from items")
        
        #所有修改完成后，触发校验
        file_record = self.db.get(FileRecord, source_file_id)
        if not file_record:
            raise ValueError("Failed to retrieve Source file")
        validation_report = self.validation_service.validate_file(file_record)
        self.db.flush()
        return validation_report
 
        
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


