"""Auth schemas for request/response validation"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Request Schemas ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Password (min 6 characters)")
    confirm_password: str = Field(..., alias="confirmPassword", description="Password confirmation")
    name: Optional[str] = Field(None, max_length=255, description="User's full name")

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Пароли не совпадают')
        return v


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Password reset token")
    password: str = Field(..., min_length=6, description="New password (min 6 characters)")
    confirm_password: str = Field(..., alias="confirmPassword", description="Password confirmation")

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Пароли не совпадают')
        return v


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., description="Email verification token")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., alias="refreshToken", description="Refresh token")


# ─── Response Schemas ─────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    role: str

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    user: UserResponse

    class Config:
        populate_by_name = True


class TokenResponse(BaseModel):
    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")

    class Config:
        populate_by_name = True


class MessageResponse(BaseModel):
    success: bool
    message: str


# ─── Role Schemas ─────────────────────────────────────────────────────────────

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleResponse(RoleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── User Schemas (detailed) ──────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role_id: int = 1  # Default to USER role


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    role_id: Optional[int] = None


class UserDetailResponse(UserBase):
    id: int
    role_id: int
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
