"""
Self-check RAG core. Run: python test_rag.py
Assert-based, no framework -> cepat cek retrieval nggak regresi tiap ubah rag.py.
"""

from rag import retrieve, close


def pasal_numbers(chunks):
    return {c["pasal"] for c in chunks if c["type"] == "batang_tubuh"}


def check(query, expected_pasal, note=""):
    chunks = retrieve(query, top_k=5)
    got = pasal_numbers(chunks)
    ok = expected_pasal in got
    status = "OK  " if ok else "FAIL"
    print(f"[{status}] '{query}' -> expect Pasal {expected_pasal}, got {sorted(got)} {note}")
    assert ok, f"Pasal {expected_pasal} nggak ketemu buat query: {query}"


def main():
    check("syarat PKWT untuk pekerjaan musiman", 5)
    # query generik "berapa pesangon PHK" ambigu -> dok ini punya ~7 formula beda per
    # alasan PHK (Pasal 40 default, 43/45/46 dst multiplier situasional). Pakai query
    # presisi (nyebut alasan) biar nggak nguji hal yang emang ambigu buat manusia juga.
    check("berapa pesangon untuk PHK karena perusahaan pailit", 47)
    check("Pasal 40", 40, note="(exact metadata filter)")
    check("apa yang dimaksud dengan Pekerja/Buruh", 1, note="(definition injection)")
    check("waktu kerja lembur berapa jam", 26)

    # cross-ref expansion: Pasal 43 (PHK efisiensi) ngerujuk Pasal 40 (rumus pesangon)
    chunks = retrieve("PHK karena efisiensi perusahaan", top_k=5)
    got = pasal_numbers(chunks)
    assert 43 in got, f"Pasal 43 nggak ketemu, got {got}"
    print(f"[OK  ] cross-ref expansion: Pasal 43 tertarik, kandidat = {sorted(got)}")

    print("\nSemua check lolos.")
    close()


if __name__ == "__main__":
    main()
