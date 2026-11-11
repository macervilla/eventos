from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    twilio_account_sid: str | None = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: SecretStr | None = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_verify_service_sid: str | None = Field(default=None, alias="TWILIO_VERIFY_SERVICE_SID")
    geo_max_resultados: int = Field(default=30, ge=10, le=100, alias="GEO_MAX_RESULTADOS")
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://eventos:eventos@localhost:5432/eventos",
        alias="DATABASE_URL",
    )
    secret_key: str = Field(default="change-me-in-dev", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    backend_cors_origins: str = Field(
        default="http://localhost:5179,http://127.0.0.1:5179",
        alias="BACKEND_CORS_ORIGINS",
    )
    frontend_public_url: str = Field(default="http://localhost:5179", alias="FRONTEND_PUBLIC_URL")
    smtp_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_HOST", "MAIL_HOST"),
    )
    smtp_port: int = Field(
        default=587,
        validation_alias=AliasChoices("SMTP_PORT", "MAIL_PORT"),
    )
    smtp_username: str | None = Field(
        default="mpcssarchivos@gmail.com",
        validation_alias=AliasChoices("SMTP_USERNAME", "MAIL_USUARIO"),
    )
    smtp_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_PASSWORD", "MAIL_CLAVE"),
    )
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_security: str | None = Field(default=None, alias="MAIL_SEGURIDAD")
    smtp_from_email: str = Field(
        default="mpcssarchivos@gmail.com",
        validation_alias=AliasChoices("SMTP_FROM_EMAIL", "MAIL_REMITENTE"),
    )
    smtp_from_name: str = Field(
        default="Eventos MPCSS",
        validation_alias=AliasChoices("SMTP_FROM_NAME", "MAIL_NOMBRE"),
    )
    zona_horaria: str = Field(default="America/Argentina/Buenos_Aires", alias="ZONA_HORARIA")
    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_clock_skew_seconds: int = Field(default=5, ge=0, le=30, alias="GOOGLE_CLOCK_SKEW_SECONDS")
    media_root: str = Field(default="/app/media", alias="MEDIA_ROOT")
    media_public_base: str = Field(default="/media", alias="MEDIA_PUBLIC_BASE")
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")

    @field_validator("google_client_id", mode="before")
    @classmethod
    def normalizar_google_client_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


settings = Settings()
