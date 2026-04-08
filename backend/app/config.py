from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

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

    pipeline_db_user: str
    pipeline_db_password: str

    auth_db_user: str
    auth_db_password: str

    secret_key: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def operator_db_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.operator_db_user,
            password=self.operator_db_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def observer_db_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.observer_db_user,
            password=self.observer_db_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def pipeline_db_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.pipeline_db_user,
            password=self.pipeline_db_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def auth_db_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.auth_db_user,
            password=self.auth_db_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


"""
Export an instantiated model
"""
settings = Settings()
