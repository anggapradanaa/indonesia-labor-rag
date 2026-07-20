FROM python:3.11-slim

WORKDIR /app

# HF Spaces jalanin container sebagai user non-root; siapin HOME/cache writable.
ENV HOME=/app \
    HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingest.py rag.py app.py warm_models.py ./
COPY qdrant_index/ ./qdrant_index/
COPY chunks.json bm25_vocab.json ./

# Bake model weights ke image saat build -> no re-download tiap Space bangun dari sleep.
RUN python warm_models.py

# HF Spaces (Docker SDK) expect port 7860.
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
