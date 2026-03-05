from openai import BaseModel
from typing import List, Dict, Any
from typing import Optional

class BatchEditItemsInput(BaseModel):

    item_type_lst: List[str]
    item_id_lst: List[str]
    updates_lst: List[Dict[str, Any]]

    operator_id: str
    
    

class BatchConfirmWarningItemsInput(BaseModel):

    item_type_lst: List[str]
    item_id_lst: List[str]

    operator_id: str
    