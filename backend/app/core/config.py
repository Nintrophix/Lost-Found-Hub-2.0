"""Application settings loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Campus Lost & Found Hub"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'lostfound.db').as_posix()}"
    sql_echo: bool = False

    upload_dir: Path = BACKEND_DIR / "uploads"
    max_upload_bytes: int = 5 * 1024 * 1024

    allowed_email_domains: Annotated[list[str], NoDecode] = Field(min_length=1)
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:4200"]
    frontend_base_url: str = "http://localhost:4200"

    session_ttl_hours: int = Field(default=168, gt=0)
    cookie_secure: bool = True
    email_verification_ttl_hours: int = Field(default=24, gt=0)
    password_reset_ttl_minutes: int = Field(default=30, gt=0)
    rate_limit_enabled: bool = True

    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "Campus Lost & Found Hub <no-reply@srmist.edu.in>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    qr_token_ttl_minutes: int = 15

    # Matching: relative weights (normalised over the signals available for a pair), score threshold
    # (0 to 100) for storing a suggestion, and how far apart lost and found dates may be.
    match_weight_category: float = Field(default=30, ge=0)
    match_weight_description: float = Field(default=25, ge=0)
    match_weight_color: float = Field(default=15, ge=0)
    match_weight_location: float = Field(default=15, ge=0)
    match_weight_date: float = Field(default=15, ge=0)
    match_threshold: float = Field(default=50, ge=0, le=100)
    match_date_window_days: int = Field(default=14, ge=2, le=365)

    @field_validator("allowed_email_domains", "cors_origins", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("allowed_email_domains")
    @classmethod
    def normalise_domains(cls, value: list[str]) -> list[str]:
        return [domain.lower().lstrip("@") for domain in value]

    @field_validator("frontend_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def check_production_safety(self) -> "Settings":
        if self.environment == "production":
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production.")
            if self.email_backend == "console":
                raise ValueError("EMAIL_BACKEND=console logs secret links and is not allowed in production.")
            if not self.rate_limit_enabled:
                raise ValueError("RATE_LIMIT_ENABLED must be true in production.")
        if self.email_backend == "smtp" and not self.smtp_host:
            raise ValueError("SMTP_HOST is required when EMAIL_BACKEND=smtp.")
        if sum(self.match_weights.values()) <= 0:
            raise ValueError("At least one MATCH_WEIGHT_* setting must be greater than zero.")
        return self

    @property
    def match_weights(self) -> dict[str, float]:
        return {
            "category": self.match_weight_category,
            "description": self.match_weight_description,
            "color": self.match_weight_color,
            "location": self.match_weight_location,
            "date": self.match_weight_date,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
