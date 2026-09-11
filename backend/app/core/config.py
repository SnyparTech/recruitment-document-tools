from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and environment variables."""

    APP_NAME: str = "Candidate Profile Automation Bot"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8002

    # Selenium Persistent Session & Visual Configuration
    SELENIUM_HEADLESS: bool = False  # Set to False so the browser screen is visible
    SELENIUM_TIMEOUT: int = 25
    LOGIN_WAIT_TIMEOUT: int = 300  # Time allowed on first run if login is needed (5 minutes)
    SELENIUM_BROWSER: str = "chrome"
    CHROME_BINARY_PATH: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    CHROME_PROFILE_DIRECTORY: str = "Profile 18"
    SELENIUM_USER_DATA_DIR: str = r"C:\Users\sriha\AppData\Local\Google\Chrome\User Data"
    CHROME_AUTOMATION_USER_DATA_DIR: str = r"C:\Users\sriha\AppData\Local\Google\Chrome\NaukriAutomation"
    SELENIUM_REMOTE_DEBUGGING_PORT: int = 9222

    # Candidate Portal URLs (Naukri Resdex Candidate Search)
    NAUKRI_BASE_URL: str = "https://www.naukri.com"
    NAUKRI_RESDEX_URL: str = "https://resdex.naukri.com"

    # LLM Configuration (Groq / Gemini)
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Security, Isolation & DLP Configuration
    LOCAL_API_KEY: Optional[str] = None
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:8002",
        "http://127.0.0.1:8002",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    ALLOWED_HOSTS: list[str] = [
        "127.0.0.1",
        "localhost",
        "testserver",
        "::1",
        "*.onrender.com",
        "*.netlify.app",
        "*.ngrok-free.app",
        "*.ngrok.io",
        "*",
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
