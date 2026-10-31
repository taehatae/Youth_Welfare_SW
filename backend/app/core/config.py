from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Youth Welfare Reverse Engineering API"
    app_version: str = "0.1.0"

    database_url: str = "sqlite:///./youth_welfare.db"

    frontend_origins: str = "http://localhost:5173"
    cookie_secure: bool = False

    welfare_api_service_key: str = ""
    welfare_api_base_url: str = ""
    welfare_sync_operator_token: str = ""

    # 실험 기능: 진단할 때 LLM(로컬 Ollama)이 정책 원문과 사용자 입력을 직접 비교한다.
    use_llm_judge: bool = False
    llm_model: str = "gemma3:4b-it-q8_0"
    ollama_url: str = "http://localhost:11434"
    llm_concurrency: int = 4
    llm_judgments_path: str = "./data/llm_judgments.json"

    # 검수를 마친 구조화 조건(data/structured_conditions.json)으로 입력값과 정책 자격을 비교한다.
    use_structured_conditions: bool = False

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
