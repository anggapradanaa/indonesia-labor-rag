import { Client } from "@gradio/client";
import { HF_SPACE, getBackendStatus } from "@/lib/space";

// Cold start Space (bangun dari sleep + load BGE-M3 & reranker) bisa > 1 menit.
export const maxDuration = 300;

// Protokol ke browser: NDJSON, satu event per baris.
//   {"type":"status","text":"..."}  -> info progres (bangunin server, dll)
//   {"type":"delta","text":"..."}   -> potongan jawaban (sudah delta, tinggal append)
//   {"type":"error","text":"..."}   -> gagal, pesan siap tampil
export type ChatEvent = { type: "status" | "delta" | "error"; text: string };

export async function POST(request: Request) {
  const { message } = await request.json();

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      let closed = false;
      let lastStatus = "";
      // status_callback @gradio/client bisa kepanggil berkali-kali (polling tiap
      // detik), bahkan setelah stream ditutup -> dedupe status & abaikan kalau closed.
      const send = (event: ChatEvent) => {
        if (closed) return;
        if (event.type === "status") {
          if (event.text === lastStatus) return;
          lastStatus = event.text;
        }
        controller.enqueue(encoder.encode(JSON.stringify(event) + "\n"));
      };

      try {
        // Cek dulu status Space: kalau error (mis. RUNTIME_ERROR), Client.connect
        // cuma bakal gagal dengan pesan generik -> kasih tahu user alasan aslinya.
        const status = await getBackendStatus();
        if (status.state === "down") {
          send({ type: "error", text: status.message });
          return;
        }
        if (status.state === "waking") {
          send({ type: "status", text: "Membangunkan server, bisa sekitar 1 menit…" });
        }

        // status_callback wajib ada supaya @gradio/client mau bangunin Space
        // yang lagi sleep (tanpa ini, connect langsung gagal 503).
        const client = await Client.connect(HF_SPACE, {
          status_callback: (s) => {
            if (s.status === "sleeping" || s.status === "starting" || s.status === "building") {
              send({ type: "status", text: "Membangunkan server, bisa sekitar 1 menit…" });
            }
          },
        });

        send({ type: "status", text: "Mencari pasal yang relevan…" });
        const submission = client.submit("/chat", { message });

        let previous = "";
        for await (const event of submission) {
          if (event.type === "data") {
            const current = String(event.data[0] ?? "");
            const delta = current.slice(previous.length);
            if (delta) send({ type: "delta", text: delta });
            previous = current;
          } else if (event.type === "status" && event.stage === "error") {
            // Exception di backend (Groq/retrieval) datang sebagai status event,
            // bukan throw -> tanpa ini jawaban kosong tanpa keterangan.
            console.error("HF Space error:", event.message);
            send({ type: "error", text: "Backend gagal memproses pertanyaan. Coba lagi sebentar lagi." });
            return;
          }
        }
        if (!previous) {
          send({ type: "error", text: "Backend tidak mengirim jawaban. Coba lagi." });
        }
      } catch (err) {
        console.error("Gagal manggil HF Space:", err);
        send({ type: "error", text: "Gagal menghubungi server backend. Coba lagi sebentar lagi." });
      } finally {
        closed = true;
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
