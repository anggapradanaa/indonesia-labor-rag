import { Client } from "@gradio/client";

const HF_SPACE = process.env.HF_SPACE || "anggapradanaa/indonesia-labor-rag";

export async function POST(request: Request) {
  const { message } = await request.json();

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      try {
        const client = await Client.connect(HF_SPACE);
        const submission = client.submit("/chat", { message });

        let previous = "";
        for await (const event of submission) {
          if (event.type === "data") {
            const current = String(event.data[0] ?? "");
            const delta = current.slice(previous.length);
            if (delta) controller.enqueue(encoder.encode(delta));
            previous = current;
          }
        }
      } catch (err) {
        console.error("Gagal manggil HF Space:", err);
        controller.enqueue(
          encoder.encode("\n\n[Error: gagal menghubungi backend, coba lagi]")
        );
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
