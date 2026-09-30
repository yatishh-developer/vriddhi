from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional
from urllib.parse import quote


class Settings(BaseSettings):
    ENVIRONMENT: str = "production"
    DATABASE_URL: Optional[str] = None
    CORS_ORIGINS: str = ""
    CORS_ALLOW_CREDENTIALS: bool = False
    ALLOWED_HOSTS: str = "*"

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Firebase Admin verifies staff identity tokens. Application Default
    # Credentials are used when FIREBASE_CREDENTIALS_PATH is not supplied.
    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_CHECK_REVOKED: bool = True

    # Database connection components (prefixed with DB_ to avoid system env collisions)
    DB_USER: Optional[str] = Field(default=None, alias="DB_USER")
    DB_PASSWORD: Optional[str] = Field(default=None, alias="DB_PASSWORD")
    DB_HOST: Optional[str] = Field(default=None, alias="DB_HOST")
    DB_PORT: int = Field(default=5432, alias="DB_PORT")
    DB_NAME: str = Field(default="postgres", alias="DB_NAME")

    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None

    # Connection pool settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 300
    DB_POOL_TIMEOUT: int = 30
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    AUTH_RATE_LIMIT_REQUESTS: int = 10
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False
    OUTBOX_POLL_INTERVAL_SECONDS: float = 1.0
    OUTBOX_BATCH_SIZE: int = 50
    OUTBOX_LEASE_SECONDS: int = 60
    OUTBOX_RETENTION_DAYS: int = 14

    model_config = ConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        extra="ignore",
        populate_by_name=True,
    )

    def get_database_url(self) -> str:
        """Construct DATABASE_URL from individual components if not provided."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        missing = [
            name for name, value in {
                "DB_USER": self.DB_USER,
                "DB_PASSWORD": self.DB_PASSWORD,
                "DB_HOST": self.DB_HOST,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(
                "DATABASE_URL or all DB_* settings are required. "
                f"Missing: {', '.join(missing)}"
            )
        # URL-encode password to handle special characters like @
        encoded_password = quote(self.DB_PASSWORD or "", safe='')
        return (
            f"postgresql+psycopg://{self.DB_USER}:{encoded_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?sslmode=require"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def allowed_hosts_list(self) -> list[str]:
        hosts = [
            host.strip()
            for host in self.ALLOWED_HOSTS.split(",")
            if host.strip()
        ]
        return hosts or ["*"]


settings = Settings()
