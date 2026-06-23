from functools import lru_cache
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    MODEL: str = "claude-sonnet-4-6"
    MAX_TOKENS: int = 8192
    PDFLATEX_PATH: str = "/Library/TeX/texbin/pdflatex"
    MAX_IMAGE_SIZE_MB: int = 20

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
