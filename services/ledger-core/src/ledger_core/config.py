from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEDGER_")

    # Connects as ledger_app, never as the migrator.
    database_url: SecretStr
    log_level: str = "INFO"
