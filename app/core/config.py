import logging
import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings
from logging.handlers import RotatingFileHandler


def get_project_root() -> Path:
    """Ищет корень проекта (momu) вверх по папкам по маркерам .env или app."""
    current_path = Path(__file__).resolve()
    for parent in [current_path] + list(current_path.parents):
        if (parent / ".env").exists() or (parent / "pyproject.toml").exists() or (parent / "app").exists():
            return parent
    return Path.cwd()


def get_docs_base_dir() -> Path:
    """Папка docs: смонтированный /docs в контейнере, иначе <project_root>/docs локально."""
    #docker_docs_dir = Path("/docs")
    #if docker_docs_dir.exists():
       # return docker_docs_dir
    return get_project_root() / "docs"



def setup_logging():
    # Папка logs лежит рядом с кодом приложения: app/logs (совпадает с email_service и .gitignore).
    # get_project_root() не используется: в контейнере /app есть в корне ФС, и корнем становился "/".
    logs_dir = Path(__file__).resolve().parents[1] / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    app_log_file = logs_dir / "app.log"
    error_log_file = logs_dir / "error.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Общий лог (INFO и выше) с ротацией (до 5 МБ, до 3 файлов бэкапа)
    info_handler = RotatingFileHandler(app_log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)

    # 2. Лог только ошибок (ERROR и выше)
    error_handler = RotatingFileHandler(error_log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # 3. Вывод в консоль Docker
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    if not root_logger.handlers:
        root_logger.addHandler(info_handler)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(console_handler)

class Settings(BaseSettings):

    BASE_DIR: Path = get_project_root()
    DOCS_DIR: Path = get_docs_base_dir()
    CONTRACTS_DIR: Path = DOCS_DIR / "contract"
    CONTRACT_TEMPLATE_PATH: Path = DOCS_DIR / "templates" / "contract_template_phys.docx"
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID")

    @field_validator("CONTRACTS_DIR", "CONTRACT_TEMPLATE_PATH", mode="before")
    @classmethod
    def _resolve_relative_to_docs_dir(cls, value):
        """
        CONTRACTS_DIR/CONTRACT_TEMPLATE_PATH могут задаваться в .env относительным
        путём (например "contract" или "templates/x.docx"). Такой путь всегда
        разрешается относительно DOCS_DIR, а не относительно текущей рабочей
        директории процесса — иначе (как было) папка создаётся внутри app/.
        Абсолютный путь (например "/mnt/storage/contracts") используется как есть,
        это позволяет полностью переопределить расположение, изменив только
        CONTRACTS_DIR.
        """
        if value is None:
            return value
        path = Path(value)
        if not path.is_absolute():
            path = get_docs_base_dir() / path
        return path

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

