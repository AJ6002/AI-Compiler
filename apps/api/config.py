from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "dev_secret_key_change_in_production"

    storage_backend: str = "local"
    local_storage_root: str = "./infrastructure/local/data/raw"

    database_url: str = "postgresql://aiconnex:aiconnex_dev_password@localhost:5432/compiler_dev"
    temporal_target: str = "localhost:7233"
    temporal_namespace: str = "default"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
