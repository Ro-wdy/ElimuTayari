"""Configuration, read from the environment (and a repo-root .env in development).

Africa's Talking sandbox is the development target: AFRICASTALKING_USERNAME
defaults to "sandbox". DATABASE_URL defaults to a local SQLite file so the
server runs with no external services; production supplies a Postgres URL.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = REPO_ROOT / "server" / "elimutayari.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite+pysqlite:///{DEFAULT_SQLITE_PATH}"
    africastalking_username: str = "sandbox"
    africastalking_api_key: str = ""
    africastalking_sender_id: str = ""  # alphanumeric SMS sender ID, e.g. "Elimu"
    africastalking_shortcode: str = ""  # two-way SMS shortcode teachers text, e.g. "13302"
    anthropic_api_key: str = ""


def get_settings() -> Settings:
    return Settings()
