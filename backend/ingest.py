"""
Ingest PP Nomor 35 Tahun 2021 -> chunk per-Pasal utuh -> embed (BGE-M3) -> Qdrant local index.

Run once (CPU cukup):
    python ingest.py

Output:
    qdrant_index/   - Qdrant local-mode index (commit ke repo, statis)
    chunks.json     - hasil chunk buat inspeksi manual
"""

import json
import math
import re
from pathlib import Path

import fitz  # PyMuPDF

PDF_PATH = Path(__file__).parent.parent / "data" / "PP Nomor 35 Tahun 2021.pdf"
INDEX_DIR = Path(__file__).parent / "qdrant_index"
CHUNKS_JSON = Path(__file__).parent / "chunks.json"
COLLECTION = "pp35_2021"

# Noise lines dari header/footer tiap halaman (kop surat, nomor halaman, cap SK).
# OCR: 'PRESIDEN' kadang jadi 'PRES iDEN'/'PRES iDEN', 'REPUBLIK' jadi 'REPUELIK', dst.
NOISE_LINE = re.compile(
    r"^(SALINAN|PRES\s*[iI]?\s*DEN|REPU[BE]LIK\s*INDONESI[A-Z,.]*|-\s?\d+\s?-|SK No \d+ [A-Z])$",
    re.IGNORECASE,
)

# Konvensi cetak Berita Negara: ujung halaman nyetak 'catchword' preview
# ('Pasal 6 . . .', 'Bagian . . .') yang keulang penuh di halaman berikutnya.
TEASER_LINE = re.compile(
    r"^(Pasal\s*\d+|BAB\s+[IVXLCM]+|Bagian\s+\S+|Paragraf\s+\S+|Ayat\s*\(?\d*l?\)?|Huruf\s*\w?)"
    r"\s*\.(\s*\.)*\.?$",
    re.IGNORECASE,
)

BAB_RE = re.compile(r"^BAB\s+([IVXLCM]+)$")
BAGIAN_RE = re.compile(r"^Bagian\s+\S+$")
PARAGRAF_RE = re.compile(r"^Paragraf\s+\S+$")
# spasi opsional: OCR kadang nempelin 'Pasal22' tanpa spasi
PASAL_HEAD_RE = re.compile(r"^Pasal\s*(\d+)$")

MIN_BODY_LEN = 20  # segmen lebih pendek dari ini = teaser footer, bukan Pasal asli


def fix_split_pasal_number(line):
    """OCR kadang split 'Pasal 11' -> 'Pasal 1 1'. Gabungin kalau polanya 'Pasal D D'."""
    m = re.match(r"^Pasal (\d) (\d)$", line)
    if m:
        return f"Pasal {m.group(1)}{m.group(2)}"
    # OCR kadang misread digit terakhir jadi huruf mirip, mis. '7' -> 'T'.
    m = re.match(r"^Pasal(\d*)T$", line)
    if m:
        return f"Pasal{m.group(1)}7"
    return line


def dedupe_catchwords(lines):
    """Buang duplikat catchword: baris pendek yang jadi prefix baris berikutnya
    (mis. '(21 Perintah' lalu '(21 Perintah dan persetujuan...')."""
    out = []
    n = len(lines)
    i = 0
    while i < n:
        line, page = lines[i]
        if i + 1 < n:
            nxt_line = lines[i + 1][0]
            if (
                len(line) >= 4
                and line != nxt_line
                and nxt_line.startswith(line)
            ):
                i += 1  # skip duplikat, teruskan ke versi lengkap
                continue
        out.append((line, page))
        i += 1
    return out


def extract_pages(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for i in range(doc.page_count):
        text = doc[i].get_text()
        lines = [l.strip() for l in text.split("\n")]
        lines = [
            fix_split_pasal_number(l)
            for l in lines
            if l and not NOISE_LINE.match(l) and not TEASER_LINE.match(l)
        ]
        pages.append({"page_num": i + 1, "lines": lines})
    doc.close()
    return pages


def split_body_and_penjelasan(pages):
    """Cari batas 'PENJELASAN' (halaman berapa pun) buat pisah badan norma vs penjelasan resmi."""
    body_lines = []
    penjelasan_lines = []
    in_penjelasan = False
    for page in pages:
        for line in page["lines"]:
            if not in_penjelasan and line == "PENJELASAN":
                in_penjelasan = True
            target = penjelasan_lines if in_penjelasan else body_lines
            target.append((line, page["page_num"]))
    return dedupe_catchwords(body_lines), dedupe_catchwords(penjelasan_lines)


def parse_body(body_lines):
    """Chunk per-Pasal UTUH (no sub-split) + tag BAB/Bagian/Paragraf + capture cross-ref."""
    chunks = []
    cur_bab = cur_bab_title = cur_bagian = cur_paragraf = None
    cur_pasal = None
    cur_page_start = None
    buf = []

    def flush():
        if cur_pasal is None:
            return
        text = "\n".join(buf).strip()
        if len(text) < MIN_BODY_LEN:
            return  # teaser/footer artifact, bukan Pasal asli
        refs = sorted(
            {int(n) for n in re.findall(r"Pasal (\d+)", text) if int(n) != cur_pasal}
        )
        chunks.append(
            {
                "id": f"pasal_{cur_pasal}",
                "type": "batang_tubuh",
                "pasal": cur_pasal,
                "bab": cur_bab,
                "bab_title": cur_bab_title,
                "bagian": cur_bagian,
                "paragraf": cur_paragraf,
                "page_start": cur_page_start,
                "text": f"Pasal {cur_pasal}\n{text}",
                "cross_refs": refs,
            }
        )

    pending_bab_title = False
    i = 0
    n = len(body_lines)
    while i < n:
        line, page_num = body_lines[i]

        if BAB_RE.match(line):
            cur_bab = BAB_RE.match(line).group(1)
            cur_bagian = None
            cur_paragraf = None
            pending_bab_title = True
            i += 1
            continue
        if pending_bab_title:
            # judul BAB biasanya baris(2) langsung setelah 'BAB X' (mis. 'KETENTUAN UMUM')
            cur_bab_title = line
            pending_bab_title = False
            i += 1
            continue
        if BAGIAN_RE.match(line):
            cur_bagian = line
            cur_paragraf = None
            i += 1
            continue
        if PARAGRAF_RE.match(line):
            cur_paragraf = line
            i += 1
            continue

        head = PASAL_HEAD_RE.match(line)
        if head:
            flush()
            cur_pasal = int(head.group(1))
            cur_page_start = page_num
            buf = []
            i += 1
            continue

        if cur_pasal is not None:
            buf.append(line)
        i += 1

    flush()

    # Dedup: kalau nomor sama muncul lagi (harusnya udah kefilter MIN_BODY_LEN,
    # tapi jaga-jaga) -> simpan versi teks terpanjang.
    by_pasal = {}
    for c in chunks:
        prev = by_pasal.get(c["pasal"])
        if prev is None or len(c["text"]) > len(prev["text"]):
            by_pasal[c["pasal"]] = c
    return [by_pasal[k] for k in sorted(by_pasal)]


def parse_penjelasan(penjelasan_lines, valid_pasal_numbers):
    """Ambil penjelasan umum + penjelasan per-Pasal (skip yang cuma 'Cukup jelas')."""
    chunks = []

    # cari titik mulai 'PASAL DEMI PASAL'
    split_idx = None
    for idx, (line, _) in enumerate(penjelasan_lines):
        if "PASAL DEMI PASAL" in line.upper():
            split_idx = idx
            break

    umum_lines = penjelasan_lines[:split_idx] if split_idx else penjelasan_lines
    umum_text = "\n".join(
        l for l, _ in umum_lines if l not in ("PENJELASAN", "ATAS", "I. UMUM")
    ).strip()
    # buang header judul PP yang keulang di awal penjelasan
    umum_text = re.sub(
        r"^PERATURAN PEMERINTAH.*?KERJA\n", "", umum_text, flags=re.DOTALL
    )
    if len(umum_text) > MIN_BODY_LEN:
        chunks.append(
            {
                "id": "penjelasan_umum",
                "type": "penjelasan_umum",
                "pasal": None,
                "bab": None,
                "bab_title": None,
                "bagian": None,
                "paragraf": None,
                "page_start": umum_lines[0][1] if umum_lines else None,
                "text": f"Penjelasan Umum PP 35/2021\n{umum_text}",
                "cross_refs": [],
            }
        )

    if split_idx is None:
        return chunks

    per_pasal_lines = penjelasan_lines[split_idx + 1 :]
    cur_pasal = None
    cur_page_start = None
    buf = []

    def flush():
        if cur_pasal is None:
            return
        text = "\n".join(buf).strip()
        if not text or text.rstrip(".") in ("Cukup jelas",):
            return  # nggak nambah info, skip
        if cur_pasal not in valid_pasal_numbers:
            return  # nomor di luar range asli (kemungkinan noise OCR)
        chunks.append(
            {
                "id": f"penjelasan_pasal_{cur_pasal}",
                "type": "penjelasan",
                "pasal": cur_pasal,
                "bab": None,
                "bab_title": None,
                "bagian": None,
                "paragraf": None,
                "page_start": cur_page_start,
                "text": f"Penjelasan Pasal {cur_pasal}\n{text}",
                "cross_refs": sorted(
                    {
                        int(n)
                        for n in re.findall(r"Pasal (\d+)", text)
                        if int(n) != cur_pasal
                    }
                ),
            }
        )

    for line, page_num in per_pasal_lines:
        head = PASAL_HEAD_RE.match(line)
        if head:
            flush()
            cur_pasal = int(head.group(1))
            cur_page_start = page_num
            buf = []
            continue
        if cur_pasal is not None:
            buf.append(line)
    flush()

    return chunks


EMBED_MODEL_NAME = "BAAI/bge-m3"
BM25_VOCAB_JSON = Path(__file__).parent / "bm25_vocab.json"

# k1/b standar BM25 (Okapi). Dipakai konsisten di ingest (dokumen) & rag.py (query).
BM25_K1 = 1.5
BM25_B = 0.75


def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def embed_dense(texts):
    """Dense embedding BGE-M3 lewat transformers mentah (hindarin FlagEmbedding/
    sentence-transformers -> keduanya narik `datasets`->pyarrow yang diblok Application
    Control policy di mesin ini). BGE-M3 dense repr = [CLS] token, L2-normalized."""
    import torch
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL_NAME)
    model = AutoModel.from_pretrained(EMBED_MODEL_NAME)
    model.eval()

    vecs = []
    batch_size = 8
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            enc = tokenizer(
                batch, padding=True, truncation=True, max_length=1024, return_tensors="pt"
            )
            out = model(**enc)
            cls = out.last_hidden_state[:, 0]  # [CLS]
            cls = torch.nn.functional.normalize(cls, p=2, dim=1)
            vecs.append(cls)
    return torch.cat(vecs, dim=0).numpy()


def build_bm25_sparse(chunks):
    """BM25 manual (bukan lib rank_bm25) supaya kita pegang token->id vocab yang bisa
    dipakai ulang di query time (rag.py) buat bikin sparse vector Qdrant yang konsisten."""
    doc_tokens = [tokenize(c["text"]) for c in chunks]
    N = len(doc_tokens)
    avgdl = sum(len(t) for t in doc_tokens) / N

    vocab = {}
    df = {}
    for tokens in doc_tokens:
        for tok in set(tokens):
            if tok not in vocab:
                vocab[tok] = len(vocab)
            df[tok] = df.get(tok, 0) + 1

    idf = {
        tok: math.log((N - d + 0.5) / (d + 0.5) + 1.0) for tok, d in df.items()
    }

    sparse_vecs = []
    for tokens in doc_tokens:
        dl = len(tokens)
        tf = {}
        for tok in tokens:
            tf[tok] = tf.get(tok, 0) + 1
        weights = {}
        for tok, f in tf.items():
            score = idf[tok] * (f * (BM25_K1 + 1)) / (
                f + BM25_K1 * (1 - BM25_B + BM25_B * dl / avgdl)
            )
            weights[vocab[tok]] = score
        sparse_vecs.append(weights)

    vocab_data = {"vocab": vocab, "idf": idf, "avgdl": avgdl, "k1": BM25_K1, "b": BM25_B}
    BM25_VOCAB_JSON.write_text(json.dumps(vocab_data, ensure_ascii=False), encoding="utf-8")
    return sparse_vecs


def embed_chunks(chunks):
    texts = [c["text"] for c in chunks]
    dense = embed_dense(texts)
    sparse = build_bm25_sparse(chunks)
    return dense, sparse


def build_qdrant_index(chunks, dense, sparse):
    from qdrant_client import QdrantClient, models

    client = QdrantClient(path=str(INDEX_DIR))
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"dense": models.VectorParams(size=len(dense[0]), distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
    )

    points = []
    for i, (chunk, dvec, svec) in enumerate(zip(chunks, dense, sparse)):
        indices = list(svec.keys())
        values = [float(w) for w in svec.values()]
        points.append(
            models.PointStruct(
                id=i,
                vector={
                    "dense": dvec.tolist(),
                    "sparse": models.SparseVector(indices=indices, values=values),
                },
                payload=chunk,
            )
        )
    client.upsert(collection_name=COLLECTION, points=points)
    client.close()


def main():
    print(f"Baca PDF: {PDF_PATH}")
    pages = extract_pages(PDF_PATH)
    body_lines, penjelasan_lines = split_body_and_penjelasan(pages)

    body_chunks = parse_body(body_lines)
    valid_pasal_numbers = {c["pasal"] for c in body_chunks}
    print(f"Pasal (batang tubuh) terbaca: {len(body_chunks)} "
          f"-> {sorted(valid_pasal_numbers)[:3]}...{sorted(valid_pasal_numbers)[-3:]}")

    penjelasan_chunks = parse_penjelasan(penjelasan_lines, valid_pasal_numbers)
    print(f"Penjelasan bermakna terbaca: {len(penjelasan_chunks)}")

    all_chunks = body_chunks + penjelasan_chunks
    total_refs = sum(len(c["cross_refs"]) for c in all_chunks)
    print(f"Total chunk: {len(all_chunks)}, total cross-ref: {total_refs}")

    CHUNKS_JSON.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Ditulis: {CHUNKS_JSON}")

    print("Embedding pakai BGE-M3 (CPU, ~1-3 menit)...")
    dense, sparse = embed_chunks(all_chunks)

    print(f"Bikin Qdrant index: {INDEX_DIR}")
    build_qdrant_index(all_chunks, dense, sparse)
    print("Selesai. Index siap di-commit.")


if __name__ == "__main__":
    main()
