# CLAUDE.md — Indonesia Labor RAG

RAG chatbot publik untuk **PP Nomor 35 Tahun 2021** (PKWT, Alih Daya, Waktu Kerja/Istirahat, PHK). User tanya bahasa Indonesia, jawaban wajib grounded + sitasi Pasal.

## Keputusan terkunci (jangan re-derive)

**Skenario: Groq serverless + $0 + no GPU.** Bukan self-host GPU, bukan Kaggle-serving.

| Layer | Pilihan | Catatan |
|---|---|---|
| LLM | Groq `llama-3.3-70b-versatile` | fallback `llama-3.1-8b-instant` saat rate limit |
| Embedding | BGE-M3 (dense) via **raw `transformers`** + BM25 manual (sparse) | lihat gotcha pyarrow di bawah |
| Reranker | BGE-reranker-v2-m3 | cross-encoder, CPU |
| Vector index | Qdrant **local file** (`qdrant_index/`) | dokumen statis → di-commit, BUKAN DB service |
| Backend | HF Spaces **SDK Gradio** (CPU gratis) | 24/7, lihat gotcha di bawah |
| Frontend | Next.js + Vercel AI SDK + shadcn/ui → Vercel | 24/7 |

- **Kenapa Groq, bukan Kaggle:** Kaggle notebook ephemeral (mati ≤12 jam, no inbound port) → nggak bisa 24/7. Groq = LLM open-source di-host, free tier, prepaid off = nggak akan nagih diam-diam.
- **Kenapa bukan Qwen 7B:** itu kompromi VRAM buat self-host. Di Groq nggak bayar VRAM → ambil 70B (lebih pinter, disiplin sitasi, nalar cross-ref).
- **GPU:** tidak dipakai di mana pun. Ingest & runtime CPU-only cukup.
- **Gotcha pyarrow:** di mesin dev ini, Windows Application Control policy blokir DLL `pyarrow` — jadi `FlagEmbedding` & `sentence-transformers` (keduanya narik `datasets`→`pyarrow`) **tidak bisa dipakai**. Solusi: dense embedding pakai `transformers.AutoModel("BAAI/bge-m3")` mentah ([CLS] token, L2-normalize) — lihat `embed_dense()` di `ingest.py`. Sparse pakai BM25 manual (bukan lib) supaya vocab/idf tersimpan di `bm25_vocab.json` dan bisa dipakai ulang konsisten di query time. Kalau pindah mesin/Kaggle (nggak ada policy block), FlagEmbedding boleh dipakai lagi — tapi transformers+BM25 manual sudah tervalidasi jalan, nggak perlu diganti kalau nggak perlu.
- **PDF ini hasil OCR, ada 3 pola corruption** yang di-handle di `ingest.py`: `(2)`→`(21)`, heading nempel tanpa spasi (`Pasal22`), digit ke-OCR jadi huruf (`Pasal4T`→ Pasal 47). Semua udah difilter/dinormalisasi — 66/66 Pasal tervalidasi lengkap, 0 gap.
- **Ada bagian PENJELASAN** (elucidation resmi, ~13 halaman) — 17 chunk bermakna (skip yang cuma "Cukup jelas"), tag `type: penjelasan`, dikaitkan ke `pasal` yang sama. Sumber grounding buat istilah yang cuma dijelasin di sini (mis. "produk baru", "demi hukum"), bukan norma mengikat — sitasi harus beda label ("Penjelasan Pasal N" vs "Pasal N").
- **Bukti nyata metadata filter wajib:** query literal "Pasal 40" di BM25 sparse GAGAL naruh pasal_40 di top-5 (kalah sama pasal lain yang nyebut "Pasal 40" berkali-kali di teksnya, IDF kata umum jadi rendah). Konfirmasi: fase 2 (`rag.py`) WAJIB deteksi pola "Pasal N" di query → exact payload filter, jangan andelin ranking semantik/BM25 buat itu.
- **Pivot Fase 4→gratis: HF Docker Spaces sekarang digembok billing/PRO** (ketemu pas nyoba beneran, bukan asumsi awal). Solusi: pindah ke **HF Space SDK Gradio** (gratis, no kartu) — `app_gradio.py` jadi entry-point HF Space (lihat frontmatter `README.md`: `sdk: gradio`, `app_file: app_gradio.py`). `app.py` (FastAPI polos) + `Dockerfile` tetap disimpen buat opsi lokal/host lain nanti, keduanya manggil logic sama di `chat_core.py` (no duplikasi). Konsekuensi: SDK Gradio nggak ada build-hook custom → model (~3GB) nggak ke-bake di image kayak rencana Docker, didownload pas Space pertama nyala (cold start lebih lama, tapi bertahan selama nggak rebuild penuh). Next.js (Fase 5) manggil Space ini lewat `@gradio/client`, BUKAN `fetch` ke endpoint `/chat` REST biasa.

## Aturan RAG khusus data ini (grounded ke isi asli)

Dokumen: 69 KB, ~58 Pasal, 11 BAB. Cross-ref TINGGI (225 sebutan Pasal, 69 "sebagaimana dimaksud"). Tanpa tabel/lampiran/OCR. Pesangon = **huruf-list prosa** ("a. masa kerja <1th: 1 bulan Upah; ...").

1. **Chunk per-Pasal UTUH — jangan sub-split.** Korpus mungil (~58 chunk). Split tengah Pasal memutus mapping huruf-list (mis. masa kerja→bulan pesangon) → jawaban numerik salah.
2. **Cross-ref expansion WAJIB.** Saat retrieve Pasal X, auto-fetch Pasal yang dirujuk di dalamnya (bukti: 225 ref). Tanpa ini jawaban bolong.
3. **Hybrid search** (BGE-M3 dense+sparse) — nangkep istilah legal eksak (PKWT/PHK) & nomor ("Pasal 40") yang di-miss semantik murni.
4. **Rerank** cross-encoder: retrieve ~20 → rerank → top 5.
5. **Parent-doc:** cari granular (ayat) tapi kasih LLM full Pasal.
6. **Metadata filter:** deteksi "Pasal N" di query → filter langsung.
7. **Definition injection:** Pasal 1 = 18 definisi, buat grounding istilah.
8. **Sitasi Pasal wajib** + prompt anti-halusinasi: "jawab hanya dari konteks, kalau tidak ada bilang tidak tahu".

## Struktur repo

```
backend/
  ingest.py        # sekali: PDF → chunk per-Pasal → cross-ref → BGE-M3 → qdrant_index/
  qdrant_index/    # HASIL ingest, di-commit (statis)
  chunks.json      # hasil chunk buat inspeksi manual
  rag.py           # embed query → hybrid → cross-ref expand → rerank → prompt+sitasi
  chat_core.py     # retrieve+prompt+Groq stream, dipake bareng app.py & app_gradio.py
  app.py           # FastAPI /chat (stream) → lokal/Docker/host lain
  app_gradio.py    # entry-point HF Space (SDK Gradio, gratis) → dipake buat deploy
  Dockerfile       # opsional, buat host yang terima Docker biasa (bukan HF free tier)
  requirements.txt
frontend/          # Next.js → Vercel
data/PP Nomor 35 Tahun 2021.pdf
```

## Alur

- **Offline (sekali):** `python ingest.py` (CPU cukup, ~1-3 mnt) → `qdrant_index/` → commit.
- **Runtime (24/7):** user → embed query → hybrid+rerank+cross-ref → prompt+konteks → Groq stream → jawaban+sitasi.

## Secret

- `GROQ_API_KEY` → HF Spaces secret (jangan hardcode).
- Vercel `BACKEND_URL` → URL HF Space.

## Build fase — SEMUA SELESAI, LIVE

1. Ingest (`ingest.py` + `qdrant_index/` + `chunks.json`) ✅
2. RAG core (`rag.py` + `test_rag.py`) ✅
3. API + Groq (`app.py`, `chat_core.py`) ✅
4. Deploy backend: **https://huggingface.co/spaces/anggapradanaa/indonesia-labor-rag** (SDK Gradio, ZeroGPU) ✅ **live**
5. Deploy frontend: **https://frontend-iota-nine-14.vercel.app** (Vercel, project `angga-yulian-adi-pradanas-projects/frontend`) ✅ **live**

Chatbot publik penuh, $0, no GPU dipunya sendiri. Deploy ulang: `cd frontend && npx vercel --prod` (Vercel) / `git push space main` dari `backend/` (HF Space, remote `space` udah ke-setup).

## Gotcha ZeroGPU (Fase 4, penting buat Space ini)

- Hardware Space = **ZeroGPU** (CPU Basic ke-lock buat akun baru, nggak bisa downgrade tanpa PRO). Kode kita CPU-only, no GPU beneran dipake.
- ZeroGPU **wajib** ada 1 fungsi ber-`@spaces.GPU` biar Space nggak error "No @spaces.GPU function detected". **AWAS:** manggil fungsi ber-decorator itu BENERAN makan kuota GPU asli (kuota gratis kecil, ~menit/hari) walau isinya cuma CPU. Solusi: decorator ditaro di fungsi dummy (`_zerogpu_startup_probe`) yang **nggak pernah dipanggil** — cuma buat lolos cek startup. Fungsi `respond()` yang beneran jalan tiap chat TETEP POLOS (no decorator) → nggak makan kuota. Lihat `app_gradio.py`.
- `requirements.txt`: jangan pin versi `torch` sembarangan — ZeroGPU cuma terima `torch` versi tertentu (cek pesan error Space kalau ganti). Jangan pin `spaces` juga — HF inject versi mereka sendiri, pin manual bikin conflict.
- Gradio SSR eksperimental (`demo.launch()` default) bikin 500 error di HF Space — matiin pakai `demo.launch(ssr_mode=False)`.

## Gotcha frontend (Fase 5)

- `@gradio/client`'s `submit(endpoint, data)` — key di object payload HARUS `parameter_name` (mis. `message`, lowercase, dari nama parameter Python), BUKAN `label` yang ditampilin UI (mis. "Message"). Cek pakai `demo.get_api_info()` kalau nama endpoint/parameter berubah.
- Next.js API route (`app/api/chat/route.ts`) convert cumulative text dari Gradio (`respond()` yield full partial tiap kali, bukan delta) jadi delta beneran (slice by previous length) sebelum di-stream ke browser — biar frontend tinggal append, nggak perlu logic replace. Stream ke browser formatnya NDJSON (`status`/`delta`/`error`).
- `Client.connect` TANPA `status_callback` nggak bangunin Space yang sleep (langsung 503). Exception di backend datang sebagai `event.type === "status"` + `stage === "error"`, bukan throw — harus di-handle eksplisit, kalau nggak jawaban kosong diam-diam.
- Error "gagal menghubungi backend" pas live (Nov 2026) ternyata Space `RUNTIME_ERROR`: container ZeroGPU gagal start di sisi HF (`OCI runtime create failed ... prestart hook`), bukan bug kode. Fix: restart / factory reboot Space dari Settings. `/api/status` sekarang nampilin status ini di UI.
- Metadata `bab` di `chunks.json` geser 1 Pasal (Pasal 1 ke-tag BAB II, dst) karena heading BAB nempel di akhir chunk sebelumnya. Range asli: PKWT 2–17, Alih Daya 18–20, Waktu Kerja 21–35, PHK 36–59.
