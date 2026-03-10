from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    
    openai_api_key: str
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.2

    
    max_steps: int = 10
    artifacts_dir: str = "artifacts"
    database_url: str = "./task_autopilot.db"

    
    max_retry_attempts: int = 3
    retry_base_delay: float = 1.0

    
    cache_enabled: bool = True

    class Config:
        env_file = ".env"


settings = Settings()