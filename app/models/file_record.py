# app/models/file_record.py
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Enum,
    Boolean,
    Integer,
    UniqueConstraint,
    func,
)
from app.db.base import Base
from app.db.enums import FileType, ParseStatus, ValidationStatus
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class FileRecord(Base):
    __tablename__ = "file_records"
    __table_args__ = (
    UniqueConstraint(
        "project_id",
        "file_type",
        "version",
        name="uq_filerecord_project_type_version"
    ),
)
    # =========
    # 🔒 Immutable facts
    # =========
    id :Mapped[str] = mapped_column(String(36), primary_key=True, comment="FileRecord UUID")

    project_id :Mapped[str] = mapped_column(String(36), nullable=False, comment="Project ID")

    file_type :Mapped[FileType] = mapped_column(
        Enum(FileType, name="file_type"),
        nullable=False,
        comment="Type of the file",
    )

    original_name :Mapped[str] = mapped_column(String(255), nullable=True, comment="Original filename uploaded by user")

    uploader_id :Mapped[str] = mapped_column(String(36), nullable=False, comment="User ID of the uploader")
    
    storage_path :Mapped[str] = mapped_column(String(500), nullable=True, comment="Storage path or URL of the file")

    file_hash :Mapped[str] = mapped_column(String(64), nullable=True, comment="SHA-256 hash of the file for integrity verification")

    version :Mapped[int] = mapped_column(Integer, nullable=True, comment="Version number of the file within the project")
    created_at :Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Creation timestamp"
    )

    # =========
    # 🔁 System-maintained fields
    # =========
    '''
    FileRecord 状态机
    parse_status:
        pending -> parsed
        pending -> failed
    '''
    parse_status :Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status"),
        nullable=False,
        default=ParseStatus.pending,
        comment="Parsing status of the FileRecord",
    )
    '''
    validation_status:
    pending → ok
        → warning → confirmed
        → blocked
    '''
    validation_status :Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status"),
        nullable=False,
        default=ValidationStatus.pending,
        comment="Validation status of the FileRecord",
    )
    '''
    True if this FileRecord has been used by CostSummary
    CostSummary 生成 → locked = True
    '''
    locked :Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if this FileRecord has been used by CostSummary",
    )

    updated_at :Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last update timestamp"
    )

    # =========
    # Optional: representation
    # =========
    def __repr__(self) -> str:
        return (
            f"<FileRecord id={self.id} "
            f"type={self.file_type.value} "
            f"parse={self.parse_status.value} "
            f"validate={self.validation_status.value}>"
        )
