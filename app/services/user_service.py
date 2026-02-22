# app/services/user_service.py
from uuid import uuid4
from typing import Optional
import bcrypt
from sqlalchemy.orm import Session
from app.models.user import User

class UserService:
    """
    Minimal user service for V0.1.
    Provides:
    - registration
    - authentication
    - password reset
    - user lookup
    - deactivation

    No RBAC / token / session management here.
    """

    def __init__(self, db: Session):
        self.db = db

    # ======================================================
    # 🔐 Internal helpers
    # ======================================================

    def _hash_password(self, password: str) -> str:
        '''Hash a password using bcrypt'''
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

    def _verify_password(self, password: str, password_hash: str) -> bool:
        '''verify a password against its hash'''
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )

    # ======================================================
    # 👤 User CRUD
    # ======================================================

    def create_user(
        self,
        *,
        account: str,
        password: str,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
    ) -> User:
        """
        Register a new user.
        
        :param account: Login account (unique)
        :type account: str
        :param password: Plaintext password
        :type password: str
        :param display_name: Display name for the user
        :type display_name: Optional[str]
        :param email: User email address
        :type email: Optional[str]
        :param phone_number: User phone number
        :type phone_number: Optional[str]
        """

        # 1️⃣ account 唯一性校验
        exists = (
            self.db.query(User)
            .filter(User.account == account)
            .first()
        )
        if exists:
            raise ValueError(f"Account '{account}' already exists")

        # 2️⃣ 创建用户
        user = User(
            id=str(uuid4()),
            account=account,
            display_name=display_name,
            password_hash=self._hash_password(password),
            email=email,
            phone_number=phone_number,
            is_active=True,
        )

        self.db.add(user)
        self.db.flush()

        return user

    def authenticate(
        self,
        *,
        account: str,
        password: str,
    ) -> User:
        """
        Authenticate user by account + password.
        Returns User if successful.
        
        :param account: Login account
        :type account: str
        :param password: Plaintext password
        :type password: str
        """

        user = (
            self.db.query(User)
            .filter(User.account == account)
            .first()
        )

        if not user:
            raise ValueError("Invalid account or password")

        if not user.is_active:
            raise PermissionError("User account is deactivated")

        if not self._verify_password(password, user.password_hash):
            raise ValueError("Invalid account or password")

        return user

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return (
            self.db.query(User)
            .filter(User.id == user_id)
            .first()
        )

    def get_user_by_account(self, account: str) -> Optional[User]:
        return (
            self.db.query(User)
            .filter(User.account == account)
            .first()
        )

    # ======================================================
    # 🔁 Account maintenance
    # ======================================================

    def reset_password(
        self,
        *,
        user_id: str,
        new_password: str,
    ) -> None:
        """
        Reset password directly.
        (V0.1: admin or trusted flow)
        
        :param user_id: ID of the user to reset password for
        :type user_id: str
        :param new_password: New plaintext password
        :type new_password: str
        """

        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        user.password_hash = self._hash_password(new_password)


    def deactivate_user(self, *, user_id: str) -> None:
        """
        Deactivate (soft delete) user.
        
        :param user_id: ID of the user to deactivate
        :type user_id: str
        """

        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        user.is_active = False
