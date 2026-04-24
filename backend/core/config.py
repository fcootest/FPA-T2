from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bq_project: str = "fpa-t-494007"
    google_application_credentials: str = ""
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
