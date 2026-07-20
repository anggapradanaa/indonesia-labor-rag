"""
RAG core: query -> hybrid search + exact Pasal filter + cross-ref expansion
          + definition injection -> rerank -> konteks siap prompt (dengan sitasi).

Semua model lewat `transformers` mentah (bukan FlagEmbedding/sentence-transformers)
-> hindarin pyarrow yang diblok Application Control policy di mesin dev ini.
Lihat CLAUDE.md bagian 'Gotcha pyarrow'.
"""

import json
import re
from pathlib import Path

from qdrant_client import QdrantClient, models

from ingest import BM25_VOCAB_JSON, COLLECTION, INDEX_DIR, embed_dense, tokenize

RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"
DEFINITION_KEYWORDS = ("apa itu", "apa yang dimaksud", "definisi", "pengertian", "arti dari")

_client = None
_vocab_data = None
_reranker = None  # (tokenizer, model), lazy-loaded


def _get_client():
    global _client
    if _client is None:
        _client = QdrantClient(path=str(INDEX_DIR))
    return _client


def _get_vocab():
    global _vocab_data
    if _vocab_data is None:
        _vocab_data = json.loads(BM25_VOCAB_JSON.read_text(encoding="utf-8"))
    return _vocab_data


def _get_reranker():
    global _reranker
    if _reranker is None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tok = AutoTokenizer.from_pretrained(RERANKER_MODEL_NAME)
        model = AutoModelForSequenceClassification.from_pretrained(RERANKER_MODEL_NAME)
        model.eval()
        _reranker = (tok, model)
    return _reranker


def _query_sparse_vector(query):
    vocab_data = _get_vocab()
    vocab, idf = vocab_data["vocab"], vocab_data["idf"]
    indices, values = [], []
    for tok in set(tokenize(query)):
        if tok in vocab:
            indices.append(vocab[tok])
            values.append(idf.get(tok, 0.0))
    return indices, values


def _detect_pasal_numbers(query):
    return sorted({int(n) for n in re.findall(r"Pasal\s*(\d+)", query, re.IGNORECASE)})


def _fetch_by_pasal(pasal_numbers, chunk_type="batang_tubuh"):
    if not pasal_numbers:
        return []
    client = _get_client()
    hits = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(key="type", match=models.MatchValue(value=chunk_type)),
                models.FieldCondition(key="pasal", match=models.MatchAny(any=pasal_numbers)),
            ]
        ),
        limit=len(pasal_numbers),
    )[0]
    return [h.payload for h in hits]


def _rrf_fuse(dense_hits, sparse_hits, k=60):
    """Reciprocal Rank Fusion: gabung 2 ranking tanpa perlu tuning bobot manual."""
    scores = {}
    payloads = {}
    for rank, hit in enumerate(dense_hits):
        cid = hit.payload["id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        payloads[cid] = hit.payload
    for rank, hit in enumerate(sparse_hits):
        cid = hit.payload["id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        payloads[cid] = hit.payload
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [payloads[cid] for cid, _ in ranked]


def _rerank(query, candidates, top_k):
    if not candidates:
        return []
    import torch

    tok, model = _get_reranker()
    pairs = [[query, c["text"]] for c in candidates]
    with torch.no_grad():
        enc = tok(pairs, padding=True, truncation=True, max_length=1024, return_tensors="pt")
        scores = model(**enc).logits.view(-1).float().tolist()
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    return [c for c, _ in ranked[:top_k]]


def retrieve(query, top_k=5, fetch_k=20):
    """Return list of chunk payload dict (udah di-rerank), siap dipakai bikin prompt+sitasi."""
    client = _get_client()

    dvec = embed_dense([query])[0]
    dense_hits = client.query_points(
        collection_name=COLLECTION, query=dvec.tolist(), using="dense", limit=fetch_k
    ).points

    s_idx, s_val = _query_sparse_vector(query)
    sparse_hits = client.query_points(
        collection_name=COLLECTION,
        query=models.SparseVector(indices=s_idx, values=s_val),
        using="sparse",
        limit=fetch_k,
    ).points

    fused = _rrf_fuse(dense_hits, sparse_hits)

    # exact metadata filter: "Pasal N" di query -> paksa masuk kandidat (jangan cuma
    # andelin ranking semantik/BM25, terbukti gagal buat lookup nomor pasal literal)
    exact = _fetch_by_pasal(_detect_pasal_numbers(query))

    candidates = {c["id"]: c for c in exact}
    for c in fused:
        candidates.setdefault(c["id"], c)

    # cross-ref expansion: pasal yang dirujuk di dalam kandidat teratas ikut ditarik
    seed_refs = set()
    for c in list(candidates.values())[: top_k * 2]:
        seed_refs.update(c.get("cross_refs", []))
    for c in _fetch_by_pasal(sorted(seed_refs)):
        candidates.setdefault(c["id"], c)

    # definition injection: query nanya definisi -> Pasal 1 (18 definisi) ikut disuntik
    if any(kw in query.lower() for kw in DEFINITION_KEYWORDS):
        for c in _fetch_by_pasal([1]):
            candidates.setdefault(c["id"], c)

    return _rerank(query, list(candidates.values()), top_k)


def build_context(chunks):
    """Susun konteks+sitasi siap tempel ke prompt LLM."""
    parts = []
    for c in chunks:
        if c["type"] == "penjelasan":
            label = f"[Penjelasan Pasal {c['pasal']}]"
        elif c["type"] == "penjelasan_umum":
            label = "[Penjelasan Umum]"
        else:
            label = f"[Pasal {c['pasal']}]"
        parts.append(f"{label}\n{c['text']}")
    return "\n\n---\n\n".join(parts)


def close():
    global _client
    if _client is not None:
        _client.close()
        _client = None
