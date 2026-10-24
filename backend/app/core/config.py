"""
PoliBrief Backend — Application Configuration
"""
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # project root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"
    SECRET_KEY: str
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"

    # Database
    DATABASE_URL: str = "sqlite:///./storage/database/polibrief.db"

    # Session / Auth
    SESSION_EXPIRE_HOURS: int = 8
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # News Collection
    COLLECTION_INTERVAL_MINUTES: int = 30
    NEWS_RETENTION_DAYS: int = 30
    FINGERPRINT_RETENTION_DAYS: int = 90
    PUBLICATION_HISTORY_RETENTION_DAYS: int = 90
    LOG_RETENTION_DAYS: int = 30

    # Meta / Facebook
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    FACEBOOK_PAGE_ID: str = ""
    FACEBOOK_PAGE_ACCESS_TOKEN: str = ""
    META_API_VERSION: str = "v21.0"

    # Storage
    STORAGE_PATH: str = "./storage"
    GENERATED_IMAGES_PATH: str = "./storage/generated"
    TEMPLATES_PATH: str = "./storage/templates"
    LOGS_PATH: str = "./storage/logs"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        example_key = "change-this-to-a-long-random-secret-key-minimum-32-chars"
        if len(value) < 32 or value == example_key:
            raise ValueError(
                "SECRET_KEY must be a stable, private value containing at least 32 characters. "
                "Set it in .env; do not use the example value."
            )
        return value

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def db_path(self) -> Path:
        """Resolve absolute path to the SQLite database file."""
        url = self.DATABASE_URL
        if url.startswith("sqlite:///./"):
            return BASE_DIR / url[len("sqlite:///./"):]
        if url.startswith("sqlite:////"):
            return Path(url[len("sqlite:////"):])
        return BASE_DIR / "storage" / "database" / "polibrief.db"

    @property
    def storage_base(self) -> Path:
        return (BASE_DIR / self.STORAGE_PATH).resolve()

    @property
    def generated_images_dir(self) -> Path:
        return (BASE_DIR / self.GENERATED_IMAGES_PATH).resolve()

    @property
    def templates_dir(self) -> Path:
        return (BASE_DIR / self.TEMPLATES_PATH).resolve()

    @property
    def logs_dir(self) -> Path:
        return (BASE_DIR / self.LOGS_PATH).resolve()


settings = Settings()
