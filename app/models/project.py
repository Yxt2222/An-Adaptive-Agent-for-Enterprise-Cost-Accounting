# app/models/project.py
from app.db.base import Base
from app.db.enums import ProjectIdentifierStatus, ProjectNameStatus
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, String, DateTime, Enum, JSON, func
from sqlalchemy.orm import Mapped, mapped_column




class Project(Base):
    __tablename__ = "projects"

    # =========
    # 🔒 Immutable facts
    # =========
    id :Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        comment = 'Project UUID')  # UUID
    raw_name : Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment = 'Original project name(immutable)')
    created_at : Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment = 'Creation timestamp')

    # =========
    # 🔁 System maintained fields
    # =========
    identifier_status : Mapped[ProjectIdentifierStatus] = mapped_column(
        Enum(ProjectIdentifierStatus, 
        name="project_identifier_status"),
        nullable=False,
        default=ProjectIdentifierStatus.pending,
        comment="Status of project identifier verification",
    )

    name_status : Mapped[ProjectNameStatus] = mapped_column(
        Enum(ProjectNameStatus, name="project_name_status"),
        nullable=False,
        default=ProjectNameStatus.pending,
        comment="Status of project name verification",
    )

    updated_at : Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last update timestamp",
    )

    # =========
    # ✍️ Business editable (with AuditLog)
    # =========
    business_code : Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True,
        comment="Business code assigned to the project(editable)",)
    contract_code : Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True,
        comment="Contract code assigned to the project(editable)",)

    normalized_name : Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Normalized project name(editable)",)
    spec_tags : Mapped[Optional[List[str]]] = mapped_column(
        JSON, 
        nullable=True,
        comment="Specification tags associated with the project(editable)",)
    # =========
    # Optional: representation
    # =========
    def __repr__(self) -> str:
        return f"<Project id={self.id} raw_name={self.raw_name}>"
