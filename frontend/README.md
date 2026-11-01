# Frontend - RAG PP Nomor 35 Tahun 2021

Next.js chat UI (shadcn/ui) yang manggil backend (HF Space, SDK Gradio) lewat
`@gradio/client`. Bukan REST `fetch` biasa — Space-nya Gradio, jadi pakai
client resmi mereka buat streaming.

## Arsitektur

```
Browser -> app/page.tsx (chat UI)
        -> GET  /api/status -> HF API runtime.stage (indikator status server)
        -> POST /api/chat (Next.js Route Handler)
             -> cek status Space dulu (error -> pesan jelas, bukan error generik)
             -> @gradio/client -> HF Space (anggapradanaa/indonesia-labor-rag)
             -> stream balik ke browser sebagai NDJSON:
                {"type":"status"|"delta"|"error","text":"..."}
```

Jawaban dirender `components/answer.tsx` (markdown ringan: paragraf, list,
**bold**) dan sitasi `(Pasal N)` / `(Penjelasan Pasal N)` jadi chip, plus
baris "Dasar hukum" di bawah tiap jawaban.

## Run lokal

```bash
npm install
# isi HF_SPACE di .env.local (lihat .env.local.example)
npm run dev
```

## Deploy ke Vercel

1. Push repo ini ke GitHub.
2. Import project di vercel.com/new, root directory: `frontend/`.
3. Set env var `HF_SPACE` = `anggapradanaa/indonesia-labor-rag` (Settings -> Environment Variables).
4. Deploy.

## Catatan

- Backend (HF Space) bisa sleep kalau idle lama -> request pertama abis sleep
  bakal lambat (cold start, model didownload ulang -- lihat `backend/README.md`).
  `Client.connect` dikasih `status_callback` supaya `@gradio/client` mau
  bangunin Space yang lagi sleep; route-nya `maxDuration = 300`.
- Kalau UI bilang "Server sedang bermasalah" (stage `RUNTIME_ERROR` dll), itu
  Space-nya yang mati, bukan frontend -> restart Space dari halaman Settings HF.
- Kalau ganti nama Space atau pindah owner, update `HF_SPACE` di Vercel env,
  redeploy.
