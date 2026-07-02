"""Application settings, loaded from environment / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://billpop:billpop@localhost:5432/billpop"
    app_env: str = "development"
    # Which eligibility clearinghouse gateway to use. Only "sandbox" exists until
    # a vendor is selected (spec open-question Q2).
    eligibility_gateway: str = "sandbox"


settings = Settings()
