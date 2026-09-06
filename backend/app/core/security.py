"""
Enterprise-Grade Local Security & Data Leakage Prevention (DLP) Module.

Provides:
- SecurityHeadersMiddleware: OWASP standard HTTP security headers.
- LocalhostGuardMiddleware: Host header validation & DNS rebinding protection.
- RateLimitMiddleware: In-memory token bucket rate limiter.
- PayloadLimitMiddleware: Request body size limiter.
- PIIMaskingFilter: Logging DLP filter masking sensitive PII and secrets.
- verify_api_key: Optional X-API-Key dependency for endpoint protection.
"""

import collections
import logging
import re
import time
from typing import Callable, Dict, List, Optional
from fastapi import HTTPException, Request, Response, Security, status
from fastapi.security.api_key import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings

logger = logging.getLogger(__name__)

# API Key security scheme for Swagger / OpenAPI docs
API_KEY_HEADER_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


# ==============================================================================
# 1. HTTP Security Headers Middleware
# ==============================================================================
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects OWASP-recommended HTTP security headers into every response.
    Prevents Clickjacking, MIME-confusion, XSS, and unauthorized framing.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        # Content Security Policy (allows Swagger UI / CDN assets while blocking malicious frames)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self';"
        )

        # Anti-Clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Anti-MIME Sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Cross-Site Scripting Filter
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (restrict dangerous browser APIs)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), payment=(), usb=()"
        )

        # Cache control for sensitive local API responses
        if request.url.path.startswith("/search") or request.url.path.startswith("/profiles"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        return response


# ==============================================================================
# 2. Localhost & DNS Rebinding Guard Middleware
# ==============================================================================
class LocalhostGuardMiddleware(BaseHTTPMiddleware):
    """
    Protects local API endpoints from DNS Rebinding and unauthorized host spoofing.
    Ensures that requests originate strictly from authorized localhost/loopback hosts.
    """

    ALLOWED_HOSTS = {
        "127.0.0.1",
        "localhost",
        "127.0.0.1:8000",
        "localhost:8000",
        "testserver",  # For pytest TestClient
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract host without port
        host_header = request.headers.get("host", "").lower().strip()

        # Check Host header
        if host_header and host_header not in self.ALLOWED_HOSTS:
            # Allow custom port variations of localhost/127.0.0.1
            host_name = host_header.split(":")[0]
            if host_name not in {"127.0.0.1", "localhost", "testserver", "::1"}:
                logger.warning(f"Blocked unauthorized Host header: '{host_header}'")
                return Response(
                    content='{"error":"FORBIDDEN_HOST","message":"Access restricted to localhost interface."}',
                    status_code=status.HTTP_403_FORBIDDEN,
                    media_type="application/json",
                )

        return await call_next(request)


# ==============================================================================
# 3. In-Memory Token Bucket Rate Limiter
# ==============================================================================
class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Prevents local Denial of Service (DoS) and excessive token consumption.
    Enforces per-client request limits using a sliding window.
    """

    _instances: List["RateLimitMiddleware"] = []

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rate_limit = requests_per_minute
        self.requests_map: Dict[str, List[float]] = collections.defaultdict(list)
        RateLimitMiddleware._instances.append(self)

    @classmethod
    def reset(cls) -> None:
        """Resets all active rate limiter windows (useful for test isolation)."""
        for instance in cls._instances:
            instance.requests_map.clear()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Bypass rate limiter for health checks
        if request.url.path in {"/health", "/docs", "/redoc", "/openapi.json"}:
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        window_start = now - 60.0

        # Filter out timestamps older than 60 seconds
        recent_timestamps = [t for t in self.requests_map[client_ip] if t > window_start]
        self.requests_map[client_ip] = recent_timestamps

        if len(recent_timestamps) >= self.rate_limit:
            logger.warning(f"Rate limit exceeded for client: {client_ip}")
            return Response(
                content='{"error":"RATE_LIMIT_EXCEEDED","message":"Too many requests. Please wait before retrying."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={"Retry-After": "10"},
            )

        self.requests_map[client_ip].append(now)
        return await call_next(request)


# ==============================================================================
# 4. Request Payload Size Limiter
# ==============================================================================
class PayloadLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects oversized payloads (> 1MB) to protect against memory exhaustion.
    """

    def __init__(self, app, max_bytes: int = 1048576):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    return Response(
                        content='{"error":"PAYLOAD_TOO_LARGE","message":"Request body exceeds maximum allowed size (1MB)."}',
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        media_type="application/json",
                    )
            except ValueError:
                pass

        return await call_next(request)


# ==============================================================================
# 5. Data Leakage Prevention (DLP) Logging Filter
# ==============================================================================
class PIIMaskingFilter(logging.Filter):
    """
    Inspects log records and automatically redacts:
    - Email addresses: john.doe@example.com -> j***@example.com
    - Phone numbers: +91 9876543210 -> +91 ******3210
    - API keys & secrets: gsk_... / Bearer tokens
    - Naukri session tokens: nauk_sid=... -> nauk_sid=[REDACTED]
    """

    # Regex patterns for sensitive data
    EMAIL_PATTERN = re.compile(r"\b([a-zA-Z0-9_.+-])[a-zA-Z0-9_.+-]*@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b")
    PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[-.\s]?)?(\d{2,3})[-.\s]?\d{3,4}[-.\s]?(\d{4})")
    TOKEN_PATTERN = re.compile(r"(gsk_[a-zA-Z0-9_-]{20,}|Bearer\s+[a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE)
    COOKIE_SECRET_PATTERN = re.compile(
        r"(nauk_sid|nauk_rt|ACCESS|encId|UNID)=([a-zA-Z0-9_%-]+)", re.IGNORECASE
    )

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.mask_sensitive_text(record.msg)
        return True

    @classmethod
    def mask_sensitive_text(cls, text: str) -> str:
        if not text:
            return text

        # Mask emails: j***@example.com
        text = cls.EMAIL_PATTERN.sub(r"\1***@\2", text)

        # Mask phone numbers: +91 ******3210
        text = cls.PHONE_PATTERN.sub(r"\1******\3", text)

        # Mask API tokens
        text = cls.TOKEN_PATTERN.sub(r"[SECRET_TOKEN_REDACTED]", text)

        # Mask session cookie values
        text = cls.COOKIE_SECRET_PATTERN.sub(r"\1=[REDACTED]", text)

        return text


# ==============================================================================
# 6. Optional Local API Key Dependency
# ==============================================================================
async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> Optional[str]:
    """
    Validates X-API-Key header if LOCAL_API_KEY is configured in settings.
    If LOCAL_API_KEY is None (default local mode), requests proceed freely.
    """
    expected_key = settings.LOCAL_API_KEY
    if not expected_key:
        return api_key

    if not api_key or api_key.strip() != expected_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key authentication header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
