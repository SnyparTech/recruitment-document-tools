import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.profiles import router as profiles_router
from app.api.search import router as search_router
from app.core.config import settings
from app.core.exceptions import ProfileBotException
from app.core.security import (
    LocalhostGuardMiddleware,
    PIIMaskingFilter,
    PayloadLimitMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)

# ------------------------------------------------------------------------------
# 1. Logging Setup with Real-Time DLP PII Redaction
# ------------------------------------------------------------------------------
if settings.ENABLE_DLP_LOG_MASKING:
    root_logger = logging.getLogger()
    pii_filter = PIIMaskingFilter()
    root_logger.addFilter(pii_filter)
    for handler in root_logger.handlers:
        handler.addFilter(pii_filter)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# 2. FastAPI Application Instance
# ------------------------------------------------------------------------------
app = FastAPI(
    title="Candidate Search Agent API - Naukri Resdex (Secured)",
    description=(
        "Backend-only Schema-Driven AI Recruitment Candidate Search Agent for Naukri Resdex.\n\n"
        "Security & Architecture Standards:\n"
        "• Hardened Localhost-Only Isolation & DNS Rebinding Shield.\n"
        "• OWASP HTTP Security Headers & Cross-Origin Attack Defense.\n"
        "• Real-Time Data Leakage Prevention (DLP) & PII Redaction.\n"
        "• In-Memory Token Bucket Rate Limiting & Payload Size Protection.\n"
        "• Requirement Agent (Groq Qwen 27B / Rule engine) converts requirements to strict SearchPlan.\n"
        "• Semantic Validation Service against resdex_schema.json.\n"
        "• Deterministic ResdexFormExecutor with decoupled selectors."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ------------------------------------------------------------------------------
# 3. Security Middlewares (Ordered Defense-in-Depth Pipeline)
# ------------------------------------------------------------------------------
# Layer 1: OWASP Security Headers (CSP, X-Frame-Options, X-Content-Type-Options)
if settings.ENABLE_SECURITY_HEADERS:
    app.add_middleware(SecurityHeadersMiddleware)

# Layer 2: Host Header & DNS Rebinding Protection
app.add_middleware(LocalhostGuardMiddleware)

# Layer 3: Payload Size Limiter (1 MB cap)
app.add_middleware(PayloadLimitMiddleware, max_bytes=settings.MAX_PAYLOAD_SIZE_BYTES)

# Layer 4: In-Memory Rate Limiter
app.add_middleware(
    RateLimitMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE
)

# Layer 5: Strict CORS Whitelist (Eliminates Wildcard '*' Risk)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------------------
# 4. Sanitized Exception Handlers (Zero Leakage of Internal Server Info)
# ------------------------------------------------------------------------------
@app.exception_handler(ProfileBotException)
async def profile_bot_exception_handler(request: Request, exc: ProfileBotException):
    """Translates internal domain exceptions into clean JSON API errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Sanitizes Pydantic input validation errors without leaking internal models."""
    errors = []
    for err in exc.errors():
        field_loc = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append(f"{field_loc}: {err.get('msg')}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Input validation failed. Please check your request parameters.",
            "details": errors,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handles standard HTTP exceptions cleanly."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP_{exc.status_code}",
            "message": exc.detail or "An HTTP error occurred.",
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catches unhandled errors and ensures stack traces are never leaked."""
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. No sensitive details are exposed.",
        },
    )


# ------------------------------------------------------------------------------
app.include_router(search_router)
app.include_router(profiles_router)


# ------------------------------------------------------------------------------
# 6. System & Health Check Endpoints
# ------------------------------------------------------------------------------
@app.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Root System Status",
    tags=["System"],
)
async def root():
    """Returns basic system status and service identifier."""
    return {
        "name": "Candidate Search Agent - Naukri Resdex",
        "status": "running",
        "security": "hardened-local",
        "docs": "/docs",
    }


@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    tags=["System"],
)
async def health():
    """Health check endpoint to confirm service operational status."""
    return {
        "status": "healthy",
        "mode": "local-secure",
    }


# ------------------------------------------------------------------------------
# 7. Mount Static Frontend Web App (/app)
# ------------------------------------------------------------------------------
import os
from fastapi.staticfiles import StaticFiles

frontend_dist = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
)
if os.path.exists(frontend_dist):
    app.mount("/app", StaticFiles(directory=frontend_dist, html=True), name="frontend")

