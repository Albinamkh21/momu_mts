import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT")

  
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

 
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://momu_redis:6379/0")
    
    # JWT Settings
    JWT_ACCESS_SECRET: str = os.getenv("JWT_ACCESS_SECRET", "your-secret-key-change-in-production")
    JWT_REFRESH_SECRET: str = os.getenv("JWT_REFRESH_SECRET", "your-refresh-secret-key-change-in-production")
    
    # Email Settings
    EMAIL_MODE: str = os.getenv("EMAIL_MODE", "file")  # 'file' or 'smtp'
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", '"MOMU" <noreply@momu.kz>')

settings = Settings()