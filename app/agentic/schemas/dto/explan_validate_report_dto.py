from pydantic import BaseModel
from typing import Dict, Any

class ExplainValidationReportInput(BaseModel):

    validation_report: Dict[str, Any]
    
class ExplainValidationReportOutput(BaseModel):

    explanation: str