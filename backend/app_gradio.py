"""
Entry-point buat HF Space (SDK: Gradio, gratis, no kartu -> Docker Spaces sekarang
digembok di balik billing/PRO). Logic sama persis kayak app.py (chat_core.py),
cuma beda pembungkus: Gradio ChatInterface kasih UI chat gratis + Next.js (Fase 5)
nanti bisa manggil Space ini lewat @gradio/client tanpa perlu endpoint FastAPI manual.
"""

import gradio as gr

from chat_core import stream_answer

try:
    # Paket `spaces` cuma ada di environment HF Space ZeroGPU. Space ini di-set
    # hardware ZeroGPU (CPU Basic ke-lock buat akun baru) tapi kode kita nggak
    # butuh GPU sama sekali. PENTING: manggil fungsi ber-@spaces.GPU beneran
    # MAKAN KUOTA GPU asli (kuota gratis kecil, ~menit/hari) walau isinya CPU-only.
    # Jadi decorator ini ditaro di fungsi DUMMY yang nggak pernah dipanggil --
    # cuma buat lolosin cek startup ZeroGPU ("No @spaces.GPU function
    # detected"), bukan buat dipanggil tiap chat.
    import spaces

    @spaces.GPU
    def _zerogpu_startup_probe():
        return True

except ImportError:
    pass


def respond(message, history):
    partial = ""
    for delta in stream_answer(message):
        partial += delta
        yield partial


demo = gr.ChatInterface(
    fn=respond,
    title="RAG PP Nomor 35 Tahun 2021 - Ketenagakerjaan",
    description=(
        "Tanya seputar PKWT, Alih Daya, Waktu Kerja/Istirahat, dan PHK. "
        "Jawaban grounded ke isi PP 35/2021 + sitasi Pasal."
    ),
    examples=[
        "Apa syarat PKWT untuk pekerjaan musiman?",
        "Berapa uang pesangon untuk PHK karena perusahaan pailit?",
        "Apa yang dimaksud dengan Pekerja/Buruh?",
    ],
)

if __name__ == "__main__":
    demo.launch(ssr_mode=False)  # SSR eksperimental Gradio bikin 500 error di HF Space
