from pydantic_settings import BaseSettings, SettingsConfigDict

"""
The base settings class for the app to use, importing the .env contents
"""
class Settings(BaseSettings):
    postgres_db: str
    postgres_host: str
    postgres_port: int

    operator_db_user: str
    operator_db_password: str

    observer_db_user: str
    observer_db_password: str

    secret_key: str
    operator_password: str
    observer_password: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def operator_db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.operator_db_user}:{self.operator_db_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def observer_db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.observer_db_user}:{self.observer_db_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


"""
Export an instantiated model
"""
settings = Settings()
