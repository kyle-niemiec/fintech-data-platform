from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

"""
The settings class that contains the environtment variables.
"""
class Settings(BaseSettings):
    event_store_db: str
    event_store_db_host: str = "event_store_db"
    event_store_db_port: int = 5433
    event_query_db_user: str
    event_query_db_password: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def event_query_db_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.event_query_db_user,
            password=self.event_query_db_password,
            host=self.event_store_db_host,
            port=self.event_store_db_port,
            database=self.event_store_db,
        )

"""
Export the instantiated settings object
"""
settings = Settings()
