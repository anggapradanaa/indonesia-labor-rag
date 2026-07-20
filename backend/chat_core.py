"""
Logic inti chat: retrieve (rag.py) -> prompt anti-halusinasi -> Groq stream.
Dipakai bareng oleh app.py (FastAPI, buat lokal/Docker) dan app_gradio.py
(buat HF Space gratis, SDK Gradio).
"""

import os

from dotenv import load_dotenv
from groq import Groq

import rag

load_dotenv()

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
PRIMARY_MODEL = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """Kamu asisten hukum yang jawab pertanyaan seputar PP Nomor 35 Tahun 2021 \
(Perjanjian Kerja Waktu Tertentu, Alih Daya, Waktu Kerja dan Waktu Istirahat, dan \
Pemutusan Hubungan Kerja).

ATURAN WAJIB:
1. Jawab HANYA berdasarkan KONTEKS yang diberikan di bawah. Jangan pakai pengetahuan \
lain di luar konteks.
2. Kalau jawaban nggak ada di konteks, bilang terus terang "Informasi ini tidak \
ditemukan dalam PP Nomor 35 Tahun 2021 (sesuai konteks yang tersedia)." Jangan mengarang.
3. Setiap klaim WAJIB disertai sitasi nomor Pasal, format: (Pasal N). Kalau sumbernya \
Penjelasan (bukan norma mengikat), tulis (Penjelasan Pasal N).
4. Jawab dalam Bahasa Indonesia, singkat dan jelas.
"""

client = Groq(api_key=GROQ_API_KEY)


def _stream_groq(message: str, context: str, model: str):
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"KONTEKS:\n{context}\n\nPERTANYAAN: {message}"},
        ],
        stream=True,
        temperature=0.1,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def stream_answer(message: str):
    """Generator string chunk. Retrieve dulu (sekali), lalu stream jawaban Groq
    (fallback ke model 8B kalau primary kena rate limit)."""
    chunks = rag.retrieve(message, top_k=5)
    context = rag.build_context(chunks)
    try:
        yield from _stream_groq(message, context, PRIMARY_MODEL)
    except Exception as e:
        if "rate_limit" in str(e).lower() or "429" in str(e):
            yield from _stream_groq(message, context, FALLBACK_MODEL)
        else:
            raise
