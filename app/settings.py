# agents/app/settings.py
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    backend_url: str = Field(default="", alias="BACKEND_URL")
    request_timeout: float = Field(default=60.0, alias="REQUEST_TIMEOUT")
    review_concurrency: int = Field(default=10, alias="AGENT_REVIEW_CONCURRENCY")
    review_deadline_seconds: float = Field(default=600.0, alias="AGENT_REVIEW_DEADLINE_SECONDS")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
