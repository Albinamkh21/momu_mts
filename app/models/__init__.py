from core.database import Base

# Импортируем все модели, чтобы они зарегистрировались в Base.metadata
from .copyright_holder import CopyrightHolder
from .track import Track
from .catalog import Catalog
from .staging_catalog import StagingCatalog

__all__ = ["Base", "CopyrightHolder", "Track", "Catalog", "StagingCatalog"]