# ============================================================
# Competitive Intelligence Briefing Crew - Dockerfile
# Multi-stage build for production
# ============================================================

FROM python:3.12-slim AS base

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy requirements first (layer cache optimization)
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────
FROM base AS runtime

WORKDIR /app

# Copy full project
COPY . .

# Create runtime directories
RUN mkdir -p logs outputs cache database knowledge_base/vectorstore

# Pre-download embedding model at build time (avoids cold-start)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Expose ports
EXPOSE 8000 8501

# Default: run both FastAPI and Streamlit via supervisord-style script
CMD ["python", "start.py"]
