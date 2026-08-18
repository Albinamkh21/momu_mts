"""Auth models: Role, User, RefreshToken, PasswordResetToken"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import Base


class Role(Base):
    __tablename__ = 'role'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    users: Mapped[list['User']] = relationship('User', back_populates='role')


class User(Base):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey('role.id', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False)
    
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_token: Mapped[Optional[str]] = mapped_column(String(255))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    role: Mapped['Role'] = relationship('Role', back_populates='users')
    refresh_tokens: Mapped[list['RefreshToken']] = relationship('RefreshToken', back_populates='user', cascade='all, delete-orphan')
    password_reset_tokens: Mapped[list['PasswordResetToken']] = relationship('PasswordResetToken', back_populates='user', cascade='all, delete-orphan')


class RefreshToken(Base):
    __tablename__ = 'refresh_token'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    device_info: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped['User'] = relationship('User', back_populates='refresh_tokens')


class PasswordResetToken(Base):
    __tablename__ = 'password_reset_token'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped['User'] = relationship('User', back_populates='password_reset_tokens')
