FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies for OpenCV and curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxrender1 libxext6 libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
# TPI sample fixtures (demo PCBAs + upload-test files) used by the
# "Ingest sample PCBAs" flow. Small text/PNG fixtures — safe to bake in.
COPY sample_data/ ./sample_data/

# Create directories for runtime (mounted via volumes in production)
RUN mkdir -p /app/data /app/ai_models/patchcore /app/ai_models/yolov8 /app/demo_data

ENV AVIP_ENV=demo
ENV AVIP_DATA_DIR=/app/data
ENV AVIP_MODELS_DIR=/app/ai_models
ENV AVIP_DEMO_DATA_DIR=/app/demo_data
# TPI multimodal provider: 'mock' (default, no network) or 'openai' (needs OPENAI_API_KEY).
ENV AVIP_TPI_LLM_PROVIDER=mock

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
