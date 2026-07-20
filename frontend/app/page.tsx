"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const EXAMPLES = [
  "Apa syarat PKWT untuk pekerjaan musiman?",
  "Berapa uang pesangon untuk PHK karena perusahaan pailit?",
  "Apa yang dimaksud dengan Pekerja/Buruh?",
];

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setInput("");
    setMessages((prev) => [
      ...prev,
      { role: "user", content: trimmed },
      { role: "assistant", content: "" },
    ]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });

      if (!res.body) throw new Error("No response body");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = {
            role: "assistant",
            content: next[next.length - 1].content + chunk,
          };
          return next;
        });
        scrollRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: "Gagal menghubungi backend. Coba lagi.",
        };
        return next;
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex h-dvh w-full max-w-2xl flex-col p-4">
      <header className="mb-4 shrink-0">
        <h1 className="text-xl font-semibold">
          RAG PP Nomor 35 Tahun 2021 - Ketenagakerjaan
        </h1>
        <p className="text-sm text-muted-foreground">
          Tanya seputar PKWT, Alih Daya, Waktu Kerja/Istirahat, dan PHK.
          Jawaban grounded ke isi PP 35/2021 + sitasi Pasal.
        </p>
      </header>

      <ScrollArea className="flex-1 rounded-lg border">
        <div className="flex flex-col gap-3 p-4">
          {messages.length === 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-sm text-muted-foreground">Contoh pertanyaan:</p>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => sendMessage(ex)}
                  className="text-left text-sm text-muted-foreground underline underline-offset-2 hover:text-foreground"
                >
                  {ex}
                </button>
              ))}
            </div>
          )}
          {messages.map((m, i) => (
            <Card
              key={i}
              className={
                m.role === "user"
                  ? "ml-auto max-w-[85%] bg-primary px-4 py-2 text-primary-foreground"
                  : "mr-auto max-w-[85%] px-4 py-2"
              }
            >
              <p className="whitespace-pre-wrap text-sm">
                {m.content || (loading && i === messages.length - 1 ? "..." : "")}
              </p>
            </Card>
          ))}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage(input);
        }}
        className="mt-4 flex shrink-0 gap-2"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ketik pertanyaan..."
          disabled={loading}
        />
        <Button type="submit" disabled={loading || !input.trim()}>
          Kirim
        </Button>
      </form>
    </div>
  );
}
