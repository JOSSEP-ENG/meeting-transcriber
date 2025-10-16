import os

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env 파일 경로 (프로젝트 루트 기준)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
print(f".env path: {env_path}")
load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    google_application_credentials: str = Field(default="", alias="GOOGLE_APPLICATION_CREDENTIALS")
    google_sheet_id: str = Field(default="", alias="GOOGLE_SHEET_ID")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_log_level: str = Field(default="info", alias="APP_LOG_LEVEL")
    default_speaker: str = Field(default="Unknown", alias="DEFAULT_SPEAKER")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
