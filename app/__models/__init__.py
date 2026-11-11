from models import Base

# Импортируем все модели, чтобы они зарегистрировались в Base.metadata
from .auth import Role, User, RefreshToken, PasswordResetToken

__all__ = [
    "Base", 
    "Role",
    "User",
    "RefreshToken",
    "PasswordResetToken"
]