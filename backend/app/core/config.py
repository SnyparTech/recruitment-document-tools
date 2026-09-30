from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and environment variables."""

    APP_VERSION: str = "1.0.0"

    # Candidate Portal URLs (Naukri Resdex Candidate Search)
    NAUKRI_RESDEX_URL: str = "https://resdex.naukri.com"

    # LLM Configuration (NVIDIA NIM / OpenRouter / Groq / Gemini) — tried in
    # that order, see RequirementAgent._provider_chain. All OpenAI-compatible.
    NVIDIA_NIM_KEY: Optional[str] = None
    NVIDIA_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    NVIDIA_API_URL: str = "https://integrate.api.nvidia.com/v1/chat/completions"

    # OpenRouter fallback (after NVIDIA). Default model chosen after testing
    # every free-tier candidate against the real production prompt —
    # stealth/space-bunny-alpha was fastest (1.5-8s) and the only one with no
    # reasoning-token overhead truncating output. NOTE: it's an anonymous
    # stealth-preview model — identity of the actual provider is undisclosed,
    # and OpenRouter's terms say prompts/completions may be retained by them.
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "stealth/space-bunny-alpha"
    OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1/chat/completions"

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
        "https://snypar-internal-tools.vercel.app",
        "https://resdex.naukri.com",
        "https://www.naukri.com",
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
    MAX_PAYLOAD_SIZE_BYTES: int = 31457280
    ENABLE_SECURITY_HEADERS: bool = True
    ENABLE_DLP_LOG_MASKING: bool = True

    # ------------------------------------------------------------------
    # Recruitment JD -> WhatsApp pipeline
    # ------------------------------------------------------------------

    # MongoDB persistence (jobs + message tracking)
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "recruitment_pipeline"

    # Gmail OAuth2 (Desktop/Installed-app flow). CLIENT_SECRETS_FILE is the JSON
    # downloaded from Google Cloud Console; TOKEN_FILE is where the resulting
    # refresh token is cached after the one-time interactive consent. Both are
    # local file paths, never committed (see .gitignore) and never logged.
    GMAIL_CLIENT_SECRETS_FILE: str = "gmail_credentials.json"
    GMAIL_TOKEN_FILE: str = "gmail_token.json"
    GMAIL_LABEL: str = "INBOX"  # Gmail label/query scope to poll for recruitment emails
    GMAIL_QUERY: str = "is:unread"  # additional Gmail search query, ANDed with the label

    # JD extraction LLM — reuses the same Groq/Gemini provider config as the
    # rest of the app (GROQ_API_KEY / GEMINI_API_KEY above); no separate keys.
    JD_EXTRACTION_MODEL: str = "openai/gpt-oss-20b"

    # Official Meta WhatsApp Business Platform (Cloud API). Never hardcode —
    # all of these are secrets/identifiers supplied via environment only.
    META_ACCESS_TOKEN: Optional[str] = None
    META_PHONE_NUMBER_ID: Optional[str] = None
    META_BUSINESS_ACCOUNT_ID: Optional[str] = None
    META_API_VERSION: str = "v19.0"
    META_WEBHOOK_VERIFY_TOKEN: Optional[str] = None
    META_API_BASE_URL: str = "https://graph.facebook.com"

    # Destination(s) for the formatted recruitment message. The official Meta
    # WhatsApp Cloud API has no "create/post to a WhatsApp Group" endpoint (see
    # meta_whatsapp_service.py) — the supported equivalent is messaging each
    # opted-in recipient's phone number individually. Comma-separated E.164
    # numbers, e.g. "+919876543210,+919812345678".
    WHATSAPP_BROADCAST_RECIPIENTS: str = ""
    WHATSAPP_TEMPLATE_NAME: Optional[str] = None  # approved template name, if sending outside the 24h session window
    WHATSAPP_TEMPLATE_LANGUAGE: str = "en_US"

    # Dry-run switch (default OFF — nothing is ever sent unless explicitly enabled).
    SEND_WHATSAPP: bool = False

    # Policy / spam gate
    WHATSAPP_MAX_MESSAGES_PER_HOUR: int = 20
    WHATSAPP_MESSAGE_MAX_CHARS: int = 4096  # Meta Cloud API text-message body limit

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
