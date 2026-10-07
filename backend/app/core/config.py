from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration and environment variables."""

    APP_VERSION: str = "1.0.0"

    # Candidate Portal URLs (Naukri Resdex Candidate Search)
    NAUKRI_RESDEX_URL: str = "https://resdex.naukri.com"

    # LLM Configuration (OpenAI / NVIDIA NIM / OpenRouter / Groq / Gemini) —
    # tried in that order, see RequirementAgent._provider_chain. All
    # OpenAI-compatible. OpenAI is first: best accuracy/cost balance for this
    # project's structured-extraction tasks (see docs/LLM_MODEL_COMPARISON.md)
    # — only used if OPENAI_API_KEY is configured, otherwise the chain skips
    # straight to the existing free-tier providers below.
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_API_URL: str = "https://api.openai.com/v1/chat/completions"

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

    # Device-lock for the Chrome extension: registration is gated by company
    # email (must end @AUTHORIZED_EMAIL_DOMAIN), one device per email — see
    # services/device_auth_service.py and POST /auth/register-device. OFF by
    # default so deploying this doesn't instantly lock everyone out with zero
    # devices registered — set DEVICE_AUTH_ENABLED=True in .env once you've
    # registered your own device (or are ready to).
    DEVICE_AUTH_ENABLED: bool = False
    AUTHORIZED_EMAIL_DOMAIN: str = "snypartech.com"

    # Outlook/Office365 SMTP — sends the one-time OTP code used to verify a
    # registering device's email actually belongs to them (see
    # services/otp_service.py). OUTLOOK_PASSWORD should be an app password,
    # not the account's normal login password. Never hardcode — env only.
    OUTLOOK_SMTP_HOST: str = "smtp.office365.com"
    OUTLOOK_SMTP_PORT: int = 587
    OUTLOOK_EMAIL: Optional[str] = None
    OUTLOOK_PASSWORD: Optional[str] = None
    DEVICE_OTP_TTL_SECONDS: int = 600
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

    # Group this business account created via POST /api/whatsapp/groups (see
    # api/whatsapp.py) and wants the recruitment pipeline to post into. If set,
    # /api/whatsapp/send posts to this group instead of broadcasting to
    # WHATSAPP_BROADCAST_RECIPIENTS individually. Requires OBA account status
    # — see meta_whatsapp_service.py module docstring.
    META_GROUP_ID: Optional[str] = None

    # Fallback destination(s) for the formatted recruitment message when no
    # META_GROUP_ID is configured (or group send fails) — messaging each
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
