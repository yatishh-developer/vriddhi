from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field
from pathlib import Path
from typing import Optional
from urllib.parse import quote


class Settings(BaseSettings):
    DATABASE_URL: Optional[str] = None

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database connection components (prefixed with DB_ to avoid system env collisions)
    DB_USER: str = Field(alias="DB_USER")
    DB_PASSWORD: str = Field(alias="DB_PASSWORD")
    DB_HOST: str = Field(alias="DB_HOST")
    DB_PORT: int = Field(default=5432, alias="DB_PORT")
    DB_NAME: str = Field(default="postgres", alias="DB_NAME")

    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None

    # Connection pool settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 300
    DB_POOL_TIMEOUT: int = 30

    model_config = ConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        extra="ignore",
        populate_by_name=True,
    )

    def get_database_url(self) -> str:
        """Construct DATABASE_URL from individual components if not provided."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        # URL-encode password to handle special characters like @
        encoded_password = quote(self.DB_PASSWORD, safe='')
        return (
            f"postgresql+psycopg://{self.DB_USER}:{encoded_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?sslmode=require"
        )


settings = Settings()
