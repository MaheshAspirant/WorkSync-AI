FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Application tier
COPY backend/ /app/
# Data tier artefacts and isolated ground truth (read-only inputs)
COPY database/ /app/database/
COPY ground_truth/ /app/ground_truth/
COPY data_generation/ /app/data_generation/

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m app.seed.load_seed --scale full && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
