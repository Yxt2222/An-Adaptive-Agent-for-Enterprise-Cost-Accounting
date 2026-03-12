from openai import BaseModel
from typing import List, Dict, Any
from typing import Optional

from app.agentic.schemas.dto.validate_report_dto import ValidationReportDTO

#Batch_edit_items_tool 输入校验
class BatchEditItemsInput(BaseModel):
    item_type_lst: List[str]
    item_id_lst: List[str]
    updates_lst: List[Dict[str, Any]]
    operator_id: str
    
#Batch_confirm_items_tool 输入校验
class BatchConfirmItemsInput(BaseModel):
    item_type_lst: List[str]
    item_id_lst: List[str]
    error_code_lst: List[str]
    operator_id: str
    
# Batch_edit_items_tool 输出定义
class BatchEditItemsOutput(BaseModel):
    edit_summary: Dict[str, Any]
    validation_report: Optional[ValidationReportDTO]
    
#Batch_confirm_items_tool 输出定义
class BatchConfirmItemOutput(BaseModel):
    confirm_summary: Dict[str, Any]
    validation_report: Optional[ValidationReportDTO]