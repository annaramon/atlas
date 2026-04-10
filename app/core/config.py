from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:32b"
    export_dir: str = "suunto-data-03042026"

    model_config = {"env_file": ".env"}


settings = Settings()
