from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Youth Welfare Reverse Engineering API"
    app_version: str = "0.1.0"

    database_url: str = "sqlite:///./youth_welfare.db"

    frontend_origins: str = "http://localhost:5173"

    welfare_api_service_key: str = ""
    welfare_api_base_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.frontend_origins.split(",")
            if origin.strip()
        ]


settings = Settings()