from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

DEFAULT_DEMO_FINANCE_USERS = (
    "james.beringer@meridian.example.com,"
    "kathy.winston@meridian.example.com,"
    "alex.ortiz@meridian.example.com"
)

"""
The settings class that contains the environtment variables.
"""
class Settings(BaseSettings):
    event_store_db: str
    event_store_db_host: str = "event_store_db"
    event_store_db_port: int = 5433
    event_query_db_user: str
    event_query_db_password: str

    oltp_db: str = "fintech_oltp"
    oltp_db_host: str = "oltp_db"
    oltp_db_port: int = 5434
    oltp_ui_reader_user: str = ""
    oltp_ui_reader_password: str = ""

    minio_endpoint: str = "http://minio:9000"
    minio_ingest_user: str = ""
    minio_ingest_secret: str = ""
    minio_landing_bucket: str = "fintech-lakehouse"

    ui_origin: str = "http://localhost:3000"
    demo_finance_users: str = DEFAULT_DEMO_FINANCE_USERS

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

    @property
    def oltp_query_db_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.oltp_ui_reader_user,
            password=self.oltp_ui_reader_password,
            host=self.oltp_db_host,
            port=self.oltp_db_port,
            database=self.oltp_db,
        )

    @property
    def demo_finance_users_list(self) -> list[str]:
        return [u.strip() for u in self.demo_finance_users.split(",") if u.strip()]

"""
Export the instantiated settings object
"""
settings = Settings()
