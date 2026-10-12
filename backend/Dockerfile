FROM python:3.13-slim

# libgl1/libglib2.0-0: required by PaddleOCR's opencv-python dependency
# (app/services/ocr_service.py, OCR for image/scanned-PDF resumes) — without
# these, importing paddleocr crashes with "libGL.so.1: cannot open shared
# object file" on Debian slim images. Render's native (non-Docker) Python
# build environment does not run as root, so apt-get in buildCommand
# silently no-ops there — Docker is what actually lets us install this.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

# --proxy-headers/--forwarded-allow-ips="*": Render terminates TLS and
# proxies to this container over its internal network — without this,
# uvicorn sees Render's internal proxy-hop IP as request.client.host for
# EVERY visitor, not the real client IP. That collapses many distinct real
# users onto a handful of shared addresses, so core/security.py's per-IP
# RateLimitMiddleware ends up rate-limiting the proxy pool's aggregate
# traffic instead of any one actual abusive client (confirmed in prod logs:
# 429s on three 10.x.x.x addresses that are Render-internal, not visitor
# IPs). forwarded_allow_ips="*" is safe here because Render's edge is the
# only thing that can reach this container directly — there's no untrusted
# path for a spoofed X-Forwarded-For to arrive from.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'"]
