import logging
import os
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dossier import router as dossier_router
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
    title="Candidate Profile Dossier Compiler API",
    description=(
        "Autonomous document intelligence compiler for candidate profiles.\n\n"
        "Features:\n"
        "• Upload Photo, Identity Proof, and Resume.\n"
        "• Multi-page PDF high-resolution rendering with PyMuPDF.\n"
        "• Generates OpenXML Word (.DOCX) dossiers in strict sequence (Photo ➔ ID Proof ➔ Resume).\n"
        "• Hardened Localhost-Only Isolation, OWASP headers, and Token-Bucket Rate Limiting."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ------------------------------------------------------------------------------
# 3. Security Middlewares (Ordered Defense-in-Depth Pipeline)
# ------------------------------------------------------------------------------
if settings.ENABLE_SECURITY_HEADERS:
    app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(LocalhostGuardMiddleware)
app.add_middleware(PayloadLimitMiddleware, max_bytes=settings.MAX_PAYLOAD_SIZE_BYTES)
app.add_middleware(
    RateLimitMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Content-Type-Options",
        "X-Frame-Options",
    ],
)

# ------------------------------------------------------------------------------
# 4. Standardized Global Exception Handlers
# ------------------------------------------------------------------------------
@app.exception_handler(ProfileBotException)
async def domain_exception_handler(request: Request, exc: ProfileBotException):
    logger.warning(f"Domain rule triggered: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "DomainValidationError",
            "message": exc.detail,
            "path": request.url.path,
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": " -> ".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    logger.warning(f"Request validation failed on {request.url.path}: {len(errors)} issues")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Input failed schema constraints.",
            "details": errors,
        },
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail,
            "status_code": exc.status_code,
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred. No sensitive data leaked.",
        },
    )

# ------------------------------------------------------------------------------
# 5. Include API Feature Routers (Dossier Compiler Only)
# ------------------------------------------------------------------------------
app.include_router(dossier_router)

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
    return {
        "name": "Candidate Profile Dossier Compiler",
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
if os.path.exists(frontend_dist):
    app.mount("/app", StaticFiles(directory=frontend_dist, html=True), name="frontend")
