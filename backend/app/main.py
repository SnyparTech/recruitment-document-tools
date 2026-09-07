import logging
import os
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dossier import router as dossier_router
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
    title="Candidate Intelligence & Dossier Compiler Suite",
    description=(
        "Unified recruitment intelligence platform combining:\n\n"
        "1. Schema-Driven AI Candidate Search Agent for Naukri Resdex.\n"
        "2. Automated Document Dossier Compiler (.DOCX OpenXML generation).\n\n"
        "Security & Architecture Standards:\n"
        "• Hardened Localhost-Only Isolation & DNS Rebinding Shield.\n"
        "• OWASP HTTP Security Headers & Cross-Origin Attack Defense.\n"
        "• Real-Time Data Leakage Prevention (DLP) & PII Redaction.\n"
        "• In-Memory Token Bucket Rate Limiting & Payload Size Protection.\n"
        "• High-resolution multi-page PDF rendering via PyMuPDF.\n"
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

# Layer 2: Strict Localhost-Only Guard (Blocks DNS Rebinding & Public IP exposure)
app.add_middleware(LocalhostGuardMiddleware)

# Layer 3: Payload Size Defense (Prevents large file DOS)
app.add_middleware(PayloadLimitMiddleware, max_bytes=settings.MAX_PAYLOAD_SIZE_BYTES)

# Layer 4: Token-Bucket Rate Limiter (Prevents rapid brute-force & API flooding)
app.add_middleware(
    RateLimitMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE
)

# Layer 5: Universal Web CORS (Vercel, Netlify, Render, ngrok, Localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    ],
)


# ------------------------------------------------------------------------------
# 4. Standardized Secure Exception Handlers
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
    """Catches unhandled errors and ensures stack traces are logged."""
    import traceback
    tb = traceback.format_exc()
    logger.error(f"Unhandled server error: {exc}\n{tb}")
    try:
        err_log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server_errors.log"))
        with open(err_log_path, "a", encoding="utf-8") as f_err:
            f_err.write(f"\n[{request.method} {request.url.path}] Unhandled error: {exc}\n{tb}\n")
    except Exception:
        pass

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": f"Server error: {str(exc)}",
            "detail": str(exc),
        },
    )


# ------------------------------------------------------------------------------
# 5. Include API Routers
# ------------------------------------------------------------------------------
app.include_router(search_router)
app.include_router(profiles_router)
app.include_router(dossier_router)


# ------------------------------------------------------------------------------
# 6. System & Health Check Endpoints
# ------------------------------------------------------------------------------
@app.api_route(
    "/",
    methods=["GET", "HEAD"],
    status_code=status.HTTP_200_OK,
    summary="Root System Status",
    tags=["System"],
)
async def root():
    """Returns basic system status and service identifier."""
    return {
        "name": "Candidate Intelligence & Dossier Compiler Suite",
        "status": "running",
        "security": "hardened-local",
        "endpoints": ["/search", "/profiles", "/dossier"],
        "docs": "/docs",
    }


@app.api_route(
    "/health",
    methods=["GET", "HEAD"],
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
frontend_dist = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)
if not os.path.exists(frontend_dist):
    frontend_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
    )

if os.path.exists(frontend_dist):
    app.mount("/app", StaticFiles(directory=frontend_dist, html=True), name="frontend")
