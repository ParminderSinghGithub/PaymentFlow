# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Copy dependency definition and source
COPY pyproject.toml README.md /app/
COPY src/ /app/src/
COPY migrations/ /app/migrations/
COPY alembic.ini /app/

# Install dependencies using pre-compiled wheels
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Create a non-root user and switch to it
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose FastAPI application port
EXPOSE 8000

# Container healthcheck using Python standard library (supports dynamic PORT)
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

# Start FastAPI server (supports dynamic Railway PORT)
CMD ["sh", "-c", "exec uvicorn paymentflow.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

