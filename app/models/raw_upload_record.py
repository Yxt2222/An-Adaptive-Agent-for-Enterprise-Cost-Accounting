# app/models/raw_upload_record.py

from operator import index

from sqlalchemy import String, DateTime, Enum, Integer,JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from uuid import uuid4

from app.db.base import Base
import enum
from app.db.enums import RawUploadStatus, FileType



class RawUploadRecord(Base):
    __tablename__ = "raw_upload_record"

    __table_args__ = (
        # 并发安全：同一 agent_run_id + file_type + version 唯一
        UniqueConstraint(
            "agent_run_id",
            "file_type",
            "version",
            name="uq_rawupload_run_type_version"
        ),
    )


    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4())
    )

    agent_run_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    original_filename: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(String, nullable= False, unique=True)

    upload_time: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now
    )
    file_type :Mapped[FileType] = mapped_column(
        Enum(FileType, name="file_type"),
        nullable=True,
        comment="Type of the file",
    )#probe成功后才有type

    version: Mapped[int] = mapped_column(Integer, default = 0)#在同类型文件重复上传时，version递增，未查验或者查验类型失败的文件type = 0)

    file_hash: Mapped[str] = mapped_column(String, nullable = False, index=True)
    size: Mapped[int] = mapped_column(Integer, nullable = False)

    status: Mapped[RawUploadStatus] = mapped_column(
        Enum(RawUploadStatus),
        default=RawUploadStatus.staged,
        index=True,
        nullable=False
    )
    
    detected_columns: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Detected column names during probe"
    )

    probe_error: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Error message if excel cannot be read"
    )