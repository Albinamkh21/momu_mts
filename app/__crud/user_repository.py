"""UserRepository — repository for working with auth models (User, Role, RefreshToken, PasswordResetToken)"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from __models.auth import User, Role, RefreshToken, PasswordResetToken


class UserRepository:
    """Repository for managing users, roles, and auth tokens"""

    def __init__(self, db: Session):
        self.db = db

    # ─── Role Methods ─────────────────────────────────────────────────────────

    def find_role_by_name(self, name: str) -> Optional[Role]:
        """Find role by name (e.g., 'USER', 'ADMIN')"""
        return self.db.execute(
            select(Role).where(Role.name == name)
        ).scalar_one_or_none()

    def get_role_by_id(self, role_id: int) -> Optional[Role]:
        """Get role by ID"""
        return self.db.execute(
            select(Role).where(Role.id == role_id)
        ).scalar_one_or_none()

    # ─── User Methods ─────────────────────────────────────────────────────────

    def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email with role relationship loaded"""
        return self.db.execute(
            select(User)
            .options(joinedload(User.role))
            .where(User.email == email)
        ).scalar_one_or_none()

    def find_by_id(self, user_id: int) -> Optional[User]:
        """Find user by ID with role relationship loaded"""
        return self.db.execute(
            select(User)
            .options(joinedload(User.role))
            .where(User.id == user_id)
        ).scalar_one_or_none()

    def find_by_verification_token(self, token: str) -> Optional[User]:
        """Find user by verification token"""
        return self.db.execute(
            select(User).where(User.verification_token == token)
        ).scalar_one_or_none()

    def create_user(
        self,
        email: str,
        password_hash: str,
        name: Optional[str],
        role_id: int,
        verification_token: Optional[str] = None
    ) -> User:
        """Create new user"""
        user = User(
            email=email,
            password_hash=password_hash,
            name=name,
            role_id=role_id,
            verification_token=verification_token,
            is_verified=False
        )
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def verify_user_email(self, user_id: int) -> None:
        """Mark user's email as verified and clear verification token"""
        user = self.find_by_id(user_id)
        if user:
            user.is_verified = True
            user.verification_token = None
            self.db.flush()

    def update_password_hash(self, user_id: int, new_password_hash: str) -> None:
        """Update user's password hash"""
        user = self.find_by_id(user_id)
        if user:
            user.password_hash = new_password_hash
            self.db.flush()

    # ─── Refresh Token Methods ────────────────────────────────────────────────

    def save_refresh_token(
        self,
        token: str,
        user_id: int,
        expires_at: datetime,
        device_info: Optional[str] = None
    ) -> RefreshToken:
        """Save refresh token to database"""
        refresh_token = RefreshToken(
            token=token,
            user_id=user_id,
            expires_at=expires_at,
            device_info=device_info
        )
        self.db.add(refresh_token)
        self.db.flush()
        return refresh_token

    def find_refresh_token(self, token: str) -> Optional[RefreshToken]:
        """Find refresh token by value"""
        return self.db.execute(
            select(RefreshToken)
            .options(joinedload(RefreshToken.user).joinedload(User.role))
            .where(RefreshToken.token == token)
        ).scalar_one_or_none()

    def delete_refresh_token(self, token: str) -> None:
        """Delete refresh token"""
        refresh_token = self.db.execute(
            select(RefreshToken).where(RefreshToken.token == token)
        ).scalar_one_or_none()
        if refresh_token:
            self.db.delete(refresh_token)
            self.db.flush()

    def delete_user_refresh_tokens(self, user_id: int) -> None:
        """Delete all refresh tokens for a user"""
        tokens = self.db.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id)
        ).scalars().all()
        for token in tokens:
            self.db.delete(token)
        self.db.flush()

    # ─── Password Reset Token Methods ─────────────────────────────────────────

    def create_password_reset_token(
        self,
        user_id: int,
        token: str,
        expires_at: datetime
    ) -> PasswordResetToken:
        """Create password reset token"""
        reset_token = PasswordResetToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        self.db.add(reset_token)
        self.db.flush()
        return reset_token

    def find_by_password_reset_token(self, token: str) -> Optional[PasswordResetToken]:
        """Find password reset token by value"""
        return self.db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == token)
        ).scalar_one_or_none()

    def delete_password_reset_tokens_by_user_id(self, user_id: int) -> None:
        """Delete all password reset tokens for a user"""
        tokens = self.db.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
        ).scalars().all()
        for token in tokens:
            self.db.delete(token)
        self.db.flush()
