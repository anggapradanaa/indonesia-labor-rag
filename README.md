# Indonesia Labor RAG

RAG chatbot publik yang jawab pertanyaan seputar **PP Nomor 35 Tahun 2021**
(Perjanjian Kerja Waktu Tertentu, Alih Daya, Waktu Kerja dan Waktu Istirahat,
dan Pemutusan Hubungan Kerja) — dalam Bahasa Indonesia, grounded ke isi
dokumen asli, wajib sitasi Pasal.

**Live demo:** https://frontend-iota-nine-14.vercel.app

## Arsitektur

```
Browser -> Next.js (Vercel)
        -> HF Space "anggapradanaa/indonesia-labor-rag" (SDK Gradio, ZeroGPU)
             -> hybrid search (BGE-M3 dense + BM25 sparse) + rerank + cross-ref expansion
             -> Groq (llama-3.3-70b-versatile) -> jawaban + sitasi Pasal
```

Semua komponen open-source / free-tier — total biaya **$0**. Nggak ada GPU
yang dipunya/disewa sendiri.

## Tech stack

| Layer | Pilihan |
|---|---|
| LLM | Groq `llama-3.3-70b-versatile` |
| Embedding | BGE-M3 (dense) + BM25 manual (sparse) |
| Reranker | BGE-reranker-v2-m3 |
| Vector index | Qdrant (local file, statis, di-commit) |
| Backend | HF Space, SDK Gradio |
| Frontend | Next.js + shadcn/ui, Vercel |

## Struktur repo

```
backend/    # ingest, RAG core, API/Gradio app -> deploy HF Space
frontend/   # chat UI -> deploy Vercel
data/       # PDF sumber (PP 35/2021)
```

Detail lengkap tiap bagian ada di README masing-masing folder:
- [`backend/README.md`](backend/README.md) — cara run/deploy backend
- [`frontend/README.md`](frontend/README.md) — cara run/deploy frontend

Keputusan arsitektur & gotcha teknis (kenapa pilih X, bukan Y) ada di
[`CLAUDE.md`](CLAUDE.md).

## Teknik RAG yang dipakai

Chunk per-Pasal utuh (bukan fixed-size), hybrid search (dense+sparse),
cross-reference expansion otomatis, reranking cross-encoder, metadata filter
buat query "Pasal N", definition injection (Pasal 1), dan sitasi wajib +
prompt anti-halusinasi. Alasan tiap teknik ada di `CLAUDE.md`.
