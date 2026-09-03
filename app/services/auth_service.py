"""Auth service for user registration, login, password reset, etc."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta,timezone
from typing import Optional, Dict, Any

import bcrypt
import jwt
from sqlalchemy.orm import Session

from __crud.user_repository import UserRepository
from __schemas.auth import (
    RegisterRequest,
    LoginRequest,
    LoginResponse,
    UserResponse,
    MessageResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenResponse
)
from services.email_service import EmailService


class AuthService:
    """Service for authentication and authorization"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        
        # Get JWT secrets from environment
        self.jwt_access_secret = os.getenv('JWT_ACCESS_SECRET', 'your-secret-key-change-in-production')
        self.jwt_refresh_secret = os.getenv('JWT_REFRESH_SECRET', 'your-refresh-secret-key-change-in-production')
        
        # Token expiration times
        self.access_token_expire_minutes = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 480))
        self.refresh_token_expire_days = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', 30))

    # ─── REGISTRATION ─────────────────────────────────────────────────────────

    async def register(self, data: RegisterRequest) -> MessageResponse:
        """Register new user"""
        # Check if user already exists
        existing_user = self.user_repo.find_by_email(data.email)
        if existing_user:
            raise ValueError('Пользователь с таким email уже существует')

        # Find default role (USER)
        role = self.user_repo.find_role_by_name('USER')
        if not role:
            raise ValueError('Роль по умолчанию не найдена в системе')

        # Hash password
        password_hash = self._hash_password(data.password)
        
        # Generate verification token
        verification_token = secrets.token_urlsafe(32)

        # Create user
        new_user = self.user_repo.create_user(
            email=data.email,
            password_hash=password_hash,
            name=data.name,
            role_id=role.id,
            verification_token=verification_token
        )
        
        self.db.commit()

        # Send verification email
        await EmailService.send_verification_email(new_user.email, verification_token)

        return MessageResponse(
            success=True,
            message='Регистрация успешна. Проверьте почту для подтверждения.'
        )

    # ─── LOGIN ────────────────────────────────────────────────────────────────

    async def login(self, data: LoginRequest, device_info: Optional[str] = None) -> LoginResponse:
        """Login user and return tokens"""
        # Find user
        user = self.user_repo.find_by_email(data.email)
        if not user:
            raise ValueError('Неверный email или пароль')

        # Verify password
        if not self._verify_password(data.password, user.password_hash):
            raise ValueError('Неверный email или пароль')

        # Check if email is verified
        if not user.is_verified:
            raise ValueError('Пожалуйста, подтвердите вашу электронную почту перед входом.')

        # Generate tokens
        access_token = self._create_access_token(user.id, user.role.name)
        refresh_token = self._create_refresh_token(user.id)

        # Save refresh token to database
        expires_at = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        self.user_repo.save_refresh_token(
            token=refresh_token,
            user_id=user.id,
            expires_at=expires_at,
            device_info=device_info
        )
        
        self.db.commit()

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                role=user.role.name
            )
        )

    # ─── EMAIL VERIFICATION ───────────────────────────────────────────────────

    async def verify_email(self, token: str) -> MessageResponse:
        """Verify user's email"""
        if not token:
            raise ValueError('Токен отсутствует')

        # Find user by verification token
        user = self.user_repo.find_by_verification_token(token)
        if not user:
            raise ValueError('Неверный или устаревший токен подтверждения')

        # Mark email as verified
        self.user_repo.verify_user_email(user.id)
        self.db.commit()

        return MessageResponse(
            success=True,
            message='Email успешно подтвержден. Теперь вы можете войти.'
        )

    # ─── FORGOT PASSWORD ──────────────────────────────────────────────────────

    async def forgot_password(self, data: ForgotPasswordRequest) -> MessageResponse:
        """Send password reset email"""
        user = self.user_repo.find_by_email(data.email)

        # Always return the same message to avoid revealing if email exists
        standard_message = 'Если этот email зарегистрирован, ссылка для восстановления будет отправлена.'

        if not user:
            return MessageResponse(
                success=True,
                message=standard_message
            )

        # Generate reset token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        # Delete old reset tokens for this user
        self.user_repo.delete_password_reset_tokens_by_user_id(user.id)

        # Create new reset token
        self.user_repo.create_password_reset_token(user.id, token, expires_at)
        self.db.commit()

        # Send password reset email
        await EmailService.send_password_reset_email(user.email, token)

        return MessageResponse(
            success=True,
            message=standard_message
        )

    # ─── RESET PASSWORD ───────────────────────────────────────────────────────

    async def reset_password(self, data: ResetPasswordRequest) -> MessageResponse:
        """Reset user's password using reset token"""
        # Find reset token
        reset_token = self.user_repo.find_by_password_reset_token(data.token)
        if not reset_token or reset_token.expires_at < datetime.now(timezone.utc):
            raise ValueError('Неверный или просроченный токен сброса пароля')

        # Hash new password
        new_password_hash = self._hash_password(data.password)

        # Update password
        self.user_repo.update_password_hash(reset_token.user_id, new_password_hash)
        
        # Delete all reset tokens for this user
        self.user_repo.delete_password_reset_tokens_by_user_id(reset_token.user_id)
        
        self.db.commit()

        return MessageResponse(
            success=True,
            message='Пароль успешно изменен. Теперь вы можете войти.'
        )

    # ─── REFRESH TOKEN ────────────────────────────────────────────────────────

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Refresh access token using refresh token"""
        # Find refresh token in database
        token_record = self.user_repo.find_refresh_token(refresh_token)
        
        if not token_record:
            raise ValueError('Неверный refresh token')
        
        # Check if token is expired
        if token_record.expires_at < datetime.utcnow():
            self.user_repo.delete_refresh_token(refresh_token)
            self.db.commit()
            raise ValueError('Refresh token истек')

        # Get user
        user = token_record.user
        if not user:
            raise ValueError('Пользователь не найден')

        # Generate new tokens
        new_access_token = self._create_access_token(user.id, user.role.name)
        new_refresh_token = self._create_refresh_token(user.id)

        # Delete old refresh token
        self.user_repo.delete_refresh_token(refresh_token)

        # Save new refresh token
        expires_at = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        self.user_repo.save_refresh_token(
            token=new_refresh_token,
            user_id=user.id,
            expires_at=expires_at,
            device_info=token_record.device_info
        )
        
        self.db.commit()

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token
        )

    # ─── HELPER METHODS ───────────────────────────────────────────────────────

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        password_bytes = password.encode('utf-8')
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        password_bytes = password.encode('utf-8')
        password_hash_bytes = password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, password_hash_bytes)

    def _create_access_token(self, user_id: int, role: str) -> str:
        """Create JWT access token"""
        payload = {
            'userId': user_id,
            'role': role,
            'exp': datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.jwt_access_secret, algorithm='HS256')

    def _create_refresh_token(self, user_id: int) -> str:
        """Create JWT refresh token"""
        payload = {
            'userId': user_id,
            'exp': datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.jwt_refresh_secret, algorithm='HS256')

    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode access token"""
        try:
            payload = jwt.decode(token, self.jwt_access_secret, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError('Access token истек')
        except jwt.InvalidTokenError:
            raise ValueError('Неверный access token')
