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
# llama-3.3-70b-versatile & llama-3.1-8b-instant dimatiin Groq 16 Agustus 2026
# (bikin semua chat error). Pengganti resmi dari halaman deprecations Groq.
# Bisa dioverride lewat env / HF Space secret tanpa ubah kode kalau nanti
# model ini dipensiunkan juga.
PRIMARY_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = os.environ.get("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")

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
        # gpt-oss = model reasoning: effort rendah biar cepat, dan reasoning-nya
        # jangan ikut dikirim (cuma butuh jawaban final di delta.content).
        extra_body={"reasoning_effort": "low", "include_reasoning": False},
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def _should_fallback(e: Exception) -> bool:
    """Rate limit, atau model primary udah nggak ada (dipensiunkan/salah nama)."""
    msg = str(e).lower()
    return any(
        key in msg
        for key in ("rate_limit", "429", "model_decommissioned", "model_not_found", "does not exist", "404")
    )


def stream_answer(message: str):
    """Generator string chunk. Retrieve dulu (sekali), lalu stream jawaban Groq
    (fallback ke model cadangan kalau primary kena rate limit / nggak tersedia)."""
    chunks = rag.retrieve(message, top_k=5)
    context = rag.build_context(chunks)
    produced = False
    try:
        for delta in _stream_groq(message, context, PRIMARY_MODEL):
            produced = True
            yield delta
    except Exception as e:
        # Jangan fallback kalau jawaban udah setengah jalan (bakal dobel).
        if produced or not _should_fallback(e):
            raise
        print(f"[chat_core] {PRIMARY_MODEL} gagal ({e}); fallback ke {FALLBACK_MODEL}")
        yield from _stream_groq(message, context, FALLBACK_MODEL)
