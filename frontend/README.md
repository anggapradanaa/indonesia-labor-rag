# Frontend - RAG PP Nomor 35 Tahun 2021

Next.js chat UI (shadcn/ui) yang manggil backend (HF Space, SDK Gradio) lewat
`@gradio/client`. Bukan REST `fetch` biasa — Space-nya Gradio, jadi pakai
client resmi mereka buat streaming.

## Arsitektur

```
Browser -> app/page.tsx (chat UI)
        -> POST /api/chat (Next.js Route Handler)
             -> @gradio/client -> HF Space (anggapradanaa/indonesia-labor-rag)
             -> stream balik ke browser (plain text, bukan SSE/AI SDK protocol)
```

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
- Kalau ganti nama Space atau pindah owner, update `HF_SPACE` di Vercel env,
  redeploy.
