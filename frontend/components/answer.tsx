import type { ReactNode } from "react";

// Sitasi dari LLM formatnya "(Pasal N)" / "(Penjelasan Pasal N)", kadang pakai
// ayat yang juga berkurung: "(Pasal 40 ayat (2))" -> izinkan 1 level kurung di dalam.
const CITATION = /\((?:Penjelasan )?Pasal \d+(?:[^()]|\([^()]*\))*\)/g;
const PASAL_REF = /(Penjelasan )?Pasal (\d+)/g;

function renderInline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  // Pecah per **bold** dulu, lalu cari sitasi di tiap potongan.
  text.split(/(\*\*[^*]+\*\*)/g).forEach((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      out.push(
        <strong key={`b${i}`} className="font-semibold text-ink">
          {part.slice(2, -2)}
        </strong>
      );
      return;
    }
    let last = 0;
    for (const m of part.matchAll(CITATION)) {
      const idx = m.index ?? 0;
      if (idx > last) out.push(part.slice(last, idx));
      out.push(
        <span
          key={`c${i}-${idx}`}
          className="mx-0.5 inline-block rounded-sm bg-seal-tint px-1.5 py-px align-baseline font-mono text-[0.78em] font-medium text-seal"
        >
          {m[0].slice(1, -1)}
        </span>
      );
      last = idx + m[0].length;
    }
    if (last < part.length) out.push(part.slice(last));
  });
  return out;
}

type Block =
  | { kind: "p"; text: string }
  | { kind: "h"; text: string }
  | { kind: "ul" | "ol"; items: string[] };

function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const prev = blocks[blocks.length - 1];
    if (!line) {
      blocks.push({ kind: "p", text: "" });
      continue;
    }
    const bullet = line.match(/^[-*•]\s+(.*)$/);
    const ordered = line.match(/^\d+[.)]\s+(.*)$/);
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    if (bullet || ordered) {
      const kind = bullet ? "ul" : "ol";
      const item = (bullet ?? ordered)![1];
      if (prev && prev.kind === kind) prev.items.push(item);
      else blocks.push({ kind, items: [item] });
    } else if (heading) {
      blocks.push({ kind: "h", text: heading[1] });
    } else if (prev && prev.kind === "p" && prev.text) {
      prev.text += " " + line;
    } else {
      blocks.push({ kind: "p", text: line });
    }
  }
  return blocks.filter((b) => b.kind !== "p" || b.text);
}

export function Answer({ text, streaming }: { text: string; streaming?: boolean }) {
  const blocks = parseBlocks(text);
  const caret = streaming ? (
    <span className="animate-caret ml-0.5 inline-block h-[1.1em] w-[2px] translate-y-[3px] bg-seal" />
  ) : null;

  return (
    <div className="space-y-3 text-[15px] leading-7 text-ink">
      {blocks.map((b, i) => {
        const isLast = i === blocks.length - 1;
        if (b.kind === "h") {
          return (
            <p key={i} className="pt-1 font-serif text-lg font-medium">
              {renderInline(b.text)}
              {isLast && caret}
            </p>
          );
        }
        if (b.kind === "p") {
          return (
            <p key={i}>
              {renderInline(b.text)}
              {isLast && caret}
            </p>
          );
        }
        const List = b.kind === "ul" ? "ul" : "ol";
        return (
          <List
            key={i}
            className={
              b.kind === "ul"
                ? "list-disc space-y-1.5 pl-5 marker:text-rule"
                : "list-decimal space-y-1.5 pl-5 marker:font-mono marker:text-[0.85em] marker:text-ink-soft"
            }
          >
            {b.items.map((item, j) => (
              <li key={j} className="pl-1">
                {renderInline(item)}
                {isLast && j === b.items.length - 1 && caret}
              </li>
            ))}
          </List>
        );
      })}
      {blocks.length === 0 && caret}
    </div>
  );
}

/** Daftar unik Pasal yang disitasi, urut nomor -> buat baris "Dasar hukum". */
export function extractCitations(text: string): string[] {
  const seen = new Map<string, number>();
  for (const cite of text.matchAll(CITATION)) {
    for (const m of cite[0].matchAll(PASAL_REF)) {
      const label = `${m[1] ? "Penjelasan " : ""}Pasal ${m[2]}`;
      seen.set(label, Number(m[2]) + (m[1] ? 0.5 : 0));
    }
  }
  return [...seen.entries()].sort((a, b) => a[1] - b[1]).map(([label]) => label);
}

