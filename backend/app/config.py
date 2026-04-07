from pydantic_settings import BaseSettings, SettingsConfigDict

"""
The base settings class for the app to use, importing the .env contents
"""
class Settings(BaseSettings):
    postgres_db: str
    postgres_host: str
    postgres_password: str
    postgres_port: int
    postgres_user: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


"""
Export an instantiated model
"""
settings = Settings()
