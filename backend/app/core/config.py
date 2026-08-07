from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM (Ollama local by default)
    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2"
    llm_temperature: float = 0.7

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    root_path: str = ""

    # CORS - comma-separated list of allowed origins for local clients
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,tauri://localhost,http://tauri.localhost"

    # Data
    data_dir: str = "./data"
    cv_dir: str = "./data/cvs"
    jobs_dir: str = "./data/jobs"
    outputs_dir: str = "./data/outputs"

    # User profile
    default_language: str = "es"

    class Config:
        env_file = ".env"


settings = Settings()
