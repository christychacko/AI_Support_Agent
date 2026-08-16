FROM python:3.11-slim

WORKDIR /srv

# System deps needed by chromadb / sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /srv/data

# Pre-build the RAG index at image build time so cold starts are fast
RUN python scripts/ingest_kb.py || true

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
