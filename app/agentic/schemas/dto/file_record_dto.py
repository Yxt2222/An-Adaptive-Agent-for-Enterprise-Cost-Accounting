from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.models.file_record import FileRecord


class FileRecordDTO(BaseModel):
    id: str
    project_id: str

    file_type: str
    version: int

    original_name: Optional[str]

    # 状态机核心字段
    parse_status: str
    validation_status: str
    locked: bool

    created_at: datetime

    # ===== 派生决策字段 =====
    is_parsed: bool
    is_validation_ok: bool
    is_ready_for_validate: bool
    is_ready_for_summary: bool
    @classmethod  
    def from_orm_model(cls, file_record: FileRecord) -> "FileRecordDTO":

        return cls(
            id=file_record.id,
            project_id=file_record.project_id,
            file_type=file_record.file_type.value,
            version=file_record.version,
            original_name=file_record.original_name,

            parse_status=file_record.parse_status.value,
            validation_status=file_record.validation_status.value,
            locked=file_record.locked,

            created_at=file_record.created_at,

            is_parsed=(file_record.parse_status.value == "parsed"),
            is_validation_ok=(file_record.validation_status.value in ["ok", "confirmed"]),
            is_ready_for_validate=(
                file_record.parse_status.value == "parsed"
                and file_record.validation_status.value == "pending"
            ),
            is_ready_for_summary=(
                file_record.parse_status.value == "parsed"
                and file_record.validation_status.value in ["ok", "confirmed"]
                and not file_record.locked
            )
        )
