"""
Download & cache model weights ke image Docker saat build (bukan runtime).
Biar container nggak download ulang tiap kali HF Space bangun dari sleep.
"""

from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

from rag import RERANKER_MODEL_NAME
from ingest import EMBED_MODEL_NAME

print(f"Warming {EMBED_MODEL_NAME} (dense embedder)...")
AutoTokenizer.from_pretrained(EMBED_MODEL_NAME)
AutoModel.from_pretrained(EMBED_MODEL_NAME)

print(f"Warming {RERANKER_MODEL_NAME} (reranker)...")
AutoTokenizer.from_pretrained(RERANKER_MODEL_NAME)
AutoModelForSequenceClassification.from_pretrained(RERANKER_MODEL_NAME)

print("Model warm-up selesai, sudah ke-cache di image.")
