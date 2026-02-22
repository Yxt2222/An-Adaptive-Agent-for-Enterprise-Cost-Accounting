# app/models/user.py
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    func,
)
from app.db.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class User(Base):
    """
    System operator (not employee).
    """

    __tablename__ = "users"

    id :Mapped[str] = mapped_column(String(36), primary_key=True, comment="User UUID")

    account :Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="Login account, immutable",
    )

    display_name :Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="Display name for the user",
    )

    password_hash :Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hashed password for authentication",
    )

    email :Mapped[str] = mapped_column(String(255), nullable=True, comment="User email address")
    email_verified :Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="Whether the email has been verified")

    phone_number :Mapped[str] = mapped_column(String(50), nullable=True, comment="User phone number")
    phone_verified :Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="Whether the phone number has been verified")
    is_active :Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="Whether the user account is active")

    created_at :Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Account creation timestamp",
    )
