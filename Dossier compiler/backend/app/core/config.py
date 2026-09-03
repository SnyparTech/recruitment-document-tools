from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and environment variables."""

    APP_NAME: str = "Candidate Profile Automation Bot"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8001

    # Selenium Persistent Session & Visual Configuration
    SELENIUM_HEADLESS: bool = False  # Set to False so the browser screen is visible
    SELENIUM_TIMEOUT: int = 20
    LOGIN_WAIT_TIMEOUT: int = 300  # Time allowed on first run if login is needed (5 minutes)
    SELENIUM_BROWSER: str = "chrome"
    SELENIUM_USER_DATA_DIR: Optional[str] = "./selenium_profile"  # Persistent profile for active sessions

    # Candidate Portal URLs (Naukri Resdex Candidate Search)
    NAUKRI_BASE_URL: str = "https://www.naukri.com"
    NAUKRI_RESDEX_URL: str = "https://resdex.naukri.com"

    # Groq LLM Configuration
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "qwen/qwen3.6-27b"
    GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"

    # Security, Isolation & DLP Configuration
    LOCAL_API_KEY: Optional[str] = None
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    RATE_LIMIT_PER_MINUTE: int = 120
    MAX_PAYLOAD_SIZE_BYTES: int = 31457280  # 30 MB for multi-file uploads (Photo + ID Proof + Resume)
    ENABLE_SECURITY_HEADERS: bool = True
    ENABLE_DLP_LOG_MASKING: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
