"""Configuration for the Autopilot automation service.

Settings are loaded from environment variables (prefixed with AUTOPILOT_)
or fall back to sensible defaults. The Tauri host passes the data directory
and Ollama URL at startup.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AutopilotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTOPILOT_", env_file=".env", extra="ignore")

    # Service
    host: str = "127.0.0.1"
    port: int = 8765

    # Shared secret required on every request (except /health) via the
    # `X-Autopilot-Token` header. Generated and passed by the Tauri host at
    # spawn time so that no other local process/user can control the
    # automation service (session cookies, LinkedIn actions, shutdown).
    auth_token: str = ""

    # Data directory (passed by Tauri host; defaults to local ./data)
    data_dir: str = "./data"

    # LLM (Ollama local)
    llm_base_url: str = "http://localhost:11434"
    llm_score_model: str = "llama3.2"   # fast scoring model (ideally :1b)
    llm_gen_model: str = "llama3.2"     # higher-quality generation model
    llm_temperature: float = 0.7

    # Pipeline limits
    max_jobs_per_run: int = 200
    score_threshold: int = 60           # only queue jobs scoring >= this
    top_n_generate: int = 10            # generate content for top N jobs

    # Discovery source: "guest" (no auth, safest) | "voyager" (auth) | "hybrid"
    discovery_source: str = "guest"

    # Daily action limits (safety against LinkedIn detection)
    max_connections_per_day: int = 15
    max_messages_per_day: int = 30
    max_applies_per_day: int = 20

    # Rate limiting (LinkedIn Voyager API)
    request_min_delay_s: float = 2.0
    request_max_delay_s: float = 5.0
    max_concurrent_requests: int = 5

    # Scheduler
    schedule_enabled: bool = False
    schedule_hour: int = 9
    schedule_minute: int = 0

    @property
    def db_path(self) -> Path:
        return Path(self.data_dir).resolve() / "autopilot.db"

    @property
    def search_criteria_path(self) -> Path:
        return Path(self.data_dir).resolve() / "search_criteria.json"

    @property
    def config_path(self) -> Path:
        return Path(self.data_dir).resolve() / "autopilot_config.json"

    def ensure_dirs(self) -> None:
        Path(self.data_dir).resolve().mkdir(parents=True, exist_ok=True)


settings = AutopilotSettings()
