FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxrender1 libxext6 libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY ai_models/ ./ai_models/
COPY demo_data/ ./demo_data/

# Create data directory for runtime storage
RUN mkdir -p /app/data

ENV AVIP_ENV=demo
ENV AVIP_DATA_DIR=/app/data
ENV AVIP_MODELS_DIR=/app/ai_models
ENV AVIP_DEMO_DATA_DIR=/app/demo_data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
