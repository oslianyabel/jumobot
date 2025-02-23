import logging
from typing import Optional

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class EnvConfig(BaseSettings):
    class Config:
        env_file = ".env"

    ENVIRONMENT: Optional[str] = None
    DATABASE_URL: Optional[str] = None
    DEV_DATABASE_URL: Optional[str] = None
    PROD_DATABASE_URL: Optional[str] = None
    TEST_DATABASE_URL: Optional[str] = None
    PUBLIC_ODOO_URL: Optional[str] = None
    PUBLIC_TOKEN_PATH: Optional[str] = None
    PUBLIC_SEARCH_PATH: Optional[str] = None
    PUBLIC_CREATE_PATH: Optional[str] = None
    PUBLIC_ODOO_CLIENT_ID: Optional[str] = None
    PUBLIC_ODOO_CLIENT_SECRET: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ACCOUNT_SID: Optional[str] = None
    AUTH_TOKEN: Optional[str] = None
    JUMO_ASSISTANT_ID: Optional[str] = None
    RESUME_ASSISTANT_ID: Optional[str] = None
    TEXT_RESUME_ASSISTANT_ID: Optional[str] = None
    EXTRACTOR_ASSISTANT_ID: Optional[str] = None
    BOT_NUMBER: Optional[str] = None
    EMAIL: Optional[str] = None
    MY_EMAIL: Optional[str] = None
    EMAIL_PASSWORD: Optional[str] = None
    EMAIL_HOST: Optional[str] = None
    DB_FORCE_ROLL_BACK: bool = False
    BOT_NUMBER: Optional[str] = None
    WORDS_LIMIT: Optional[int] = None


def get_config():
    config = EnvConfig()
    if config.ENVIRONMENT == "dev":
        config.DATABASE_URL = config.DEV_DATABASE_URL
    elif config.ENVIRONMENT == "prod":
        config.DATABASE_URL = config.PROD_DATABASE_URL
    else:
        config.DATABASE_URL = config.TEST_DATABASE_URL

    return config


if __name__ == "__main__":
    print(get_config().DATABASE_URL)
