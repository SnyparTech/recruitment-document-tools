FROM python:3.13-slim

# tesseract-ocr: required by app/services/ocr_service.py to OCR image and
# scanned-PDF resumes. Render's native (non-Docker) Python build environment
# does not run as root, so apt-get in buildCommand silently no-ops there —
# Docker is what actually lets us install this system dependency.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
