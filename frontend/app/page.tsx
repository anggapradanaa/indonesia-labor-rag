"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, RotateCcw, SquarePen } from "lucide-react";
import { Answer, extractCitations } from "@/components/answer";
import type { ChatEvent } from "@/app/api/chat/route";
import type { BackendStatus } from "@/lib/space";

type ChatMessage =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; status?: string; error?: string; done: boolean };

const TOPICS = [
  {
    bab: "II",
    title: "Perjanjian Kerja Waktu Tertentu",
    short: "PKWT",
    pasal: "Pasal 2–17",
    questions: [
      "Apa syarat PKWT untuk pekerjaan musiman?",
      "Berapa uang kompensasi saat PKWT berakhir?",
    ],
  },
  {
    bab: "III",
    title: "Alih Daya",
    short: "Alih Daya",
    pasal: "Pasal 18–20",
    questions: ["Siapa yang bertanggung jawab atas perlindungan pekerja alih daya?"],
  },
  {
    bab: "IV",
    title: "Waktu Kerja dan Waktu Istirahat",
    short: "Waktu Kerja",
    pasal: "Pasal 21–35",
    questions: [
      "Berapa batas maksimal waktu kerja lembur?",
      "Siapa yang berhak mendapat istirahat panjang?",
    ],
  },
  {
    bab: "V",
    title: "Pemutusan Hubungan Kerja",
    short: "PHK",
    pasal: "Pasal 36–59",
    questions: [
      "Berapa uang pesangon untuk PHK karena perusahaan pailit?",
      "Bagaimana aturan surat peringatan sebelum PHK?",
    ],
  },
];

const REPO_URL = "https://github.com/anggapradanaa/indonesia-labor-rag";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [backend, setBackend] = useState<BackendStatus | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const stickToBottom = useRef(true);

  const refreshStatus = useCallback(() => {
    fetch("/api/status")
      .then((r) => r.json())
      .then(setBackend)
      .catch(() => setBackend(null));
  }, []);

  useEffect(refreshStatus, [refreshStatus]);

  // Auto-scroll hanya kalau user memang lagi di bawah (nggak ganggu yang scroll ke atas).
  useEffect(() => {
    const el = scrollRef.current;
    if (el && messages.length > 0 && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  function updateLast(patch: (m: Extract<ChatMessage, { role: "assistant" }>) => Partial<ChatMessage>) {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last?.role === "assistant") next[next.length - 1] = { ...last, ...patch(last) } as ChatMessage;
      return next;
    });
  }

  async function ask(question: string, history: ChatMessage[]) {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    stickToBottom.current = true;
    setInput("");
    setMessages([
      ...history,
      { role: "user", content: trimmed },
      { role: "assistant", content: "", done: false },
    ]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line) as ChatEvent;
          if (event.type === "delta") {
            updateLast((m) => ({ content: m.content + event.text, status: undefined }));
          } else if (event.type === "status") {
            updateLast(() => ({ status: event.text }));
          } else {
            updateLast(() => ({ error: event.text, status: undefined }));
          }
        }
      }
    } catch {
      updateLast(() => ({
        error: "Tidak bisa terhubung ke server. Periksa koneksi lalu coba lagi.",
        status: undefined,
      }));
    } finally {
      updateLast(() => ({ done: true }));
      setLoading(false);
      refreshStatus();
      inputRef.current?.focus();
    }
  }

  function retry() {
    const question = messages[messages.length - 2];
    if (question?.role === "user") ask(question.content, messages.slice(0, -2));
  }

  function resizeInput() {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  useEffect(resizeInput, [input]);

  const empty = messages.length === 0;

  return (
    <div className="flex h-dvh flex-col bg-paper lg:flex-row">
      {/* ---------- Kolom kiri: identitas dokumen ---------- */}
      <aside className="shrink-0 border-b border-rule bg-paper-deep lg:flex lg:h-dvh lg:w-[340px] lg:flex-col lg:border-r lg:border-b-0">
        <div className="flex items-center justify-between gap-4 px-5 py-4 lg:block lg:px-8 lg:pt-10 lg:pb-0">
          <div>
            <p className="font-mono text-[11px] tracking-[0.18em] text-seal uppercase">
              Peraturan Pemerintah
            </p>
            <h1 className="mt-1 font-serif text-2xl leading-tight font-medium tracking-tight text-ink lg:mt-3 lg:text-[2.6rem] lg:leading-[1.05]">
              Nomor 35
              <br className="hidden lg:block" /> Tahun 2021
            </h1>
          </div>
          <StatusPill status={backend} className="lg:hidden" />
        </div>

        <p className="hidden px-8 pt-4 font-serif text-[15px] leading-6 text-ink-soft italic lg:block">
          tentang Perjanjian Kerja Waktu Tertentu, Alih Daya, Waktu Kerja dan Waktu
          Istirahat, dan Pemutusan Hubungan Kerja
        </p>

        <nav className="hidden px-8 pt-8 lg:block">
          <p className="mb-2 font-mono text-[11px] tracking-[0.18em] text-ink-soft uppercase">
            Cakupan
          </p>
          <ol className="border-t border-rule">
            {TOPICS.map((t) => (
              <li
                key={t.bab}
                className="grid grid-cols-[2.25rem_1fr] items-baseline border-b border-rule py-2.5"
              >
                <span className="font-mono text-xs text-seal">{t.bab}</span>
                <span>
                  <span className="block text-sm leading-5 text-ink">{t.title}</span>
                  <span className="font-mono text-[11px] text-ink-soft">{t.pasal}</span>
                </span>
              </li>
            ))}
          </ol>
        </nav>

        <div className="mt-auto hidden space-y-4 px-8 pb-8 text-xs leading-5 text-ink-soft lg:block">
          <StatusPill status={backend} />
          <p>
            Pertanyaan dicocokkan ke seluruh Pasal dan Penjelasan PP 35/2021 (pencarian
            hybrid + rerank), lalu dijawab GPT-OSS 120B (via Groq) hanya dari teks yang ditemukan.
          </p>
          <p>
            Bukan nasihat hukum. Cek kembali Pasal yang dirujuk sebelum mengambil
            keputusan.{" "}
            <a href={REPO_URL} className="underline decoration-rule underline-offset-2 hover:text-ink">
              Kode sumber
            </a>
          </p>
        </div>
      </aside>

      {/* ---------- Kolom kanan: percakapan ---------- */}
      <main className="flex min-h-0 flex-1 flex-col">
        <div
          ref={scrollRef}
          onScroll={(e) => {
            const el = e.currentTarget;
            stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          }}
          className="flex-1 overflow-y-auto"
        >
          <div className="mx-auto w-full max-w-3xl px-5 py-8 lg:px-10 lg:py-14">
            {empty ? (
              <EmptyState onPick={(q) => ask(q, [])} />
            ) : (
              <div className="space-y-10">
                {messages.map((m, i) =>
                  m.role === "user" ? (
                    <section key={i} className={i > 0 ? "border-t border-rule pt-10" : ""}>
                      <Label>Pertanyaan</Label>
                      <p className="mt-2 font-serif text-2xl leading-snug text-ink">
                        {m.content}
                      </p>
                    </section>
                  ) : (
                    <AssistantMessage
                      key={i}
                      message={m}
                      onRetry={i === messages.length - 1 && !loading ? retry : undefined}
                    />
                  )
                )}
              </div>
            )}
          </div>
        </div>

        {/* ---------- Kolom input ---------- */}
        <div className="shrink-0 border-t border-rule bg-paper">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              ask(input, messages);
            }}
            className="mx-auto w-full max-w-3xl px-5 py-4 lg:px-10"
          >
            <div className="flex items-end gap-2 rounded-md border border-rule bg-card p-2 transition-colors focus-within:border-ink-soft">
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    ask(input, messages);
                  }
                }}
                placeholder="Tulis pertanyaan tentang PKWT, alih daya, waktu kerja, atau PHK…"
                className="max-h-[200px] min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-[15px] leading-6 text-ink outline-none placeholder:text-ink-soft/70"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                aria-label="Kirim pertanyaan"
                className="grid size-10 shrink-0 place-items-center rounded bg-ink text-paper transition hover:bg-seal disabled:cursor-not-allowed disabled:bg-rule disabled:text-ink-soft"
              >
                <ArrowUp className="size-5" strokeWidth={2} />
              </button>
            </div>
            <div className="mt-2 flex items-center justify-between gap-4 px-1 text-[11px] text-ink-soft">
              <span>
                Tiap pertanyaan dijawab terpisah, tanpa mengingat pertanyaan sebelumnya.
              </span>
              {!empty && (
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => setMessages([])}
                  className="inline-flex shrink-0 items-center gap-1 hover:text-ink disabled:opacity-50"
                >
                  <SquarePen className="size-3.5" /> Mulai ulang
                </button>
              )}
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[11px] tracking-[0.18em] text-ink-soft uppercase">{children}</p>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div>
      <h2 className="max-w-xl font-serif text-4xl leading-[1.1] font-medium tracking-tight text-ink lg:text-5xl">
        Tanyakan isi peraturannya, dapatkan Pasalnya.
      </h2>
      <p className="mt-4 max-w-xl text-[15px] leading-7 text-ink-soft">
        Setiap jawaban disusun hanya dari teks PP 35/2021 dan menyebut Pasal sumbernya,
        misalnya <span className="rounded-sm bg-seal-tint px-1.5 py-px font-mono text-[0.8em] text-seal">Pasal 40</span>.
        Kalau jawabannya tidak ada di peraturan, akan dibilang tidak ada.
      </p>

      <div className="mt-12 grid gap-x-10 gap-y-8 sm:grid-cols-2">
        {TOPICS.map((t) => (
          <div key={t.bab}>
            <p className="flex items-baseline gap-2 border-b border-ink pb-2">
              <span className="font-mono text-xs text-seal">{t.bab}</span>
              <span className="text-sm font-medium text-ink">{t.short}</span>
              <span className="ml-auto font-mono text-[11px] text-ink-soft">{t.pasal}</span>
            </p>
            <ul>
              {t.questions.map((q) => (
                <li key={q} className="border-b border-rule">
                  <button
                    onClick={() => onPick(q)}
                    className="group flex w-full items-start justify-between gap-3 py-3 text-left text-[15px] leading-6 text-ink-soft transition-colors hover:text-ink"
                  >
                    <span>{q}</span>
                    <span className="translate-y-px font-mono text-xs text-rule transition-colors group-hover:text-seal">
                      →
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function AssistantMessage({
  message,
  onRetry,
}: {
  message: Extract<ChatMessage, { role: "assistant" }>;
  onRetry?: () => void;
}) {
  const { content, status, error, done } = message;
  const citations = done ? extractCitations(content) : [];
  const waiting = !done && !content;

  return (
    <section>
      <Label>Jawaban</Label>
      <div className="mt-3 border-l-2 border-seal pl-5">
        {waiting && (
          <div>
            <p className="text-sm text-ink-soft">{status ?? "Menghubungi server…"}</p>
            <div className="mt-3 h-px w-40 overflow-hidden bg-rule">
              <div className="animate-scan h-px w-1/3 bg-seal" />
            </div>
          </div>
        )}

        {content && <Answer text={content} streaming={!done} />}

        {error && (
          <div className={content ? "mt-4" : ""}>
            <p className="text-[15px] leading-7 text-seal">{error}</p>
            {onRetry && (
              <button
                onClick={onRetry}
                className="mt-2 inline-flex items-center gap-1.5 rounded border border-rule px-3 py-1.5 text-xs text-ink transition-colors hover:border-ink"
              >
                <RotateCcw className="size-3.5" /> Coba lagi
              </button>
            )}
          </div>
        )}

        {citations.length > 0 && (
          <p className="mt-5 flex flex-wrap items-baseline gap-x-2 gap-y-1 border-t border-rule pt-3 font-mono text-[11px] text-ink-soft">
            <span className="tracking-[0.18em] uppercase">Dasar hukum</span>
            {citations.map((c) => (
              <span key={c} className="text-seal">
                {c}
              </span>
            ))}
          </p>
        )}
      </div>
    </section>
  );
}

function StatusPill({ status, className = "" }: { status: BackendStatus | null; className?: string }) {
  const tone =
    status?.state === "ready"
      ? { dot: "bg-ok", short: "Aktif", text: "Server aktif" }
      : status?.state === "waking"
        ? { dot: "bg-warn", short: "Tidur", text: "Server tidur, respons pertama lebih lambat" }
        : status?.state === "down"
          ? { dot: "bg-seal", short: "Gangguan", text: "Server sedang bermasalah" }
          : { dot: "bg-rule", short: "…", text: status ? "Status tidak diketahui" : "Mengecek server…" };

  return (
    <p
      title={status?.message}
      className={`inline-flex shrink-0 items-center gap-2 font-mono text-[11px] text-ink-soft ${className}`}
    >
      <span className={`size-1.5 shrink-0 rounded-full ${tone.dot}`} />
      <span className="sm:hidden">{tone.short}</span>
      <span className="hidden sm:inline">{tone.text}</span>
    </p>
  );
}
