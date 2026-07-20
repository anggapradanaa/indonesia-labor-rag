---
title: Indonesia Labor RAG - PP 35/2021
emoji: ⚖️
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 5.9.1
app_file: app_gradio.py
---

# Backend - RAG PP Nomor 35 Tahun 2021

Chat UI + API buat tanya-jawab seputar PKWT, Alih Daya, Waktu Kerja, dan PHK
berdasarkan PP 35/2021. Lihat `../CLAUDE.md` buat detail arsitektur.

Dua entry-point, dua kegunaan beda:
- `app_gradio.py` — dipake di HF Space (SDK **Gradio**, gratis, no kartu).
  Docker Spaces sekarang digembok di balik billing/PRO, jadi pivot ke sini.
  Kasih UI chat + API otomatis (lewat `@gradio/client`, dipakai Next.js Fase 5).
- `app.py` — FastAPI polos, buat run lokal / kalau nanti pindah host lain
  (Docker/Render/dst) yang nerima `Dockerfile` biasa.

Keduanya manggil logic yang sama di `chat_core.py` (nggak ada duplikasi).

## Deploy ke Hugging Face Spaces (gratis, CPU, 24/7, SDK Gradio)

HF Space itu **repo git sendiri** — bukan subfolder dari repo utama. Jadi isi
folder `backend/` ini yang di-push ke Space, bukan seluruh `indonesia-labor-rag`.

1. Bikin Space baru di huggingface.co/new-space:
   - SDK: **Gradio**
   - Hardware: **CPU Basic** (free tier)
   - Visibility: Public
2. Set secret (Space -> Settings -> Variables and secrets):
   - `GROQ_API_KEY` = key dari console.groq.com
3. Push isi folder `backend/` ini ke repo Space:
   ```bash
   cd backend
   git init
   git remote add space https://huggingface.co/spaces/<username>/<space-name>
   git add .
   git commit -m "deploy backend"
   git push space main
   ```
4. Space bakal install `requirements.txt` lalu jalanin `app_gradio.py`
   (~2-5 menit build pertama). Jalan di `https://<username>-<space-name>.hf.space`.
5. Test: buka URL-nya di browser, coba chat lewat UI.

## Catatan

- `qdrant_index/`, `chunks.json`, `bm25_vocab.json` = hasil `ingest.py` (statis,
  dokumen nggak berubah) — udah ke-commit, Space nggak perlu re-ingest.
- **Beda sama rencana Docker sebelumnya:** SDK Gradio nggak punya build-hook
  custom, jadi model (BGE-M3 + reranker, ~3GB) **nggak ke-bake** di image —
  didownload dari HF Hub pas Space pertama nyala. Cold start lumayan (beberapa
  menit pertama kali), tapi bertahan selama Space nggak di-rebuild penuh.
- Free CPU Space bisa sleep kalau idle lama; wake-up dari sleep (bukan
  rebuild) biasanya masih pegang cache model yang udah kedownload.
- Next.js (Fase 5) manggil Space ini pakai `@gradio/client` (npm), bukan
  `fetch` biasa ke `/chat` — beda dari asumsi awal pas masih Docker/FastAPI.
- Dockerfile & `app.py` tetap disimpen (udah tervalidasi jalan lokal + Docker)
  buat opsi kalau nanti upgrade PRO/pindah host lain.

## Run lokal

```bash
pip install -r requirements.txt
# isi GROQ_API_KEY di .env (lihat .env.example)

# opsi 1: FastAPI polos
uvicorn app:app --reload

# opsi 2: Gradio (sama kayak yang jalan di HF Space)
python app_gradio.py
```
