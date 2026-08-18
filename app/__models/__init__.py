from core.database import Base

# Импортируем все модели, чтобы они зарегистрировались в Base.metadata
from .copyright_holder import CopyrightHolder
from .track import Track
from .catalog import Catalog
from .staging_catalog import StagingCatalog
from .auth import Role, User, RefreshToken, PasswordResetToken

__all__ = [
    "Base", 
    "CopyrightHolder", 
    "Track", 
    "Catalog", 
    "StagingCatalog",
    "Role",
    "User",
    "RefreshToken",
    "PasswordResetToken"
]