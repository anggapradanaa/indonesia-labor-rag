export const HF_SPACE =
  process.env.HF_SPACE || "anggapradanaa/indonesia-labor-rag";

export type BackendState = "ready" | "waking" | "down" | "unknown";

export type BackendStatus = {
  state: BackendState;
  stage: string | null;
  message: string;
};

// Stage dari HF API (runtime.stage). Selain yang di bawah (RUNTIME_ERROR,
// BUILD_ERROR, CONFIG_ERROR, PAUSED, NO_APP_FILE, ...) dianggap "down":
// Space nggak akan nyala sendiri, harus di-restart manual dari settings HF.
const READY = new Set(["RUNNING", "RUNNING_BUILDING"]);
const WAKING = new Set(["SLEEPING", "STOPPED", "BUILDING", "APP_STARTING", "RUNNING_APP_STARTING"]);

export async function getBackendStatus(): Promise<BackendStatus> {
  try {
    const res = await fetch(`https://huggingface.co/api/spaces/${HF_SPACE}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) throw new Error(`HF API ${res.status}`);
    const data = await res.json();
    const stage: string | null = data?.runtime?.stage ?? null;

    if (stage && READY.has(stage)) {
      return { state: "ready", stage, message: "Server aktif" };
    }
    if (stage && WAKING.has(stage)) {
      return {
        state: "waking",
        stage,
        message: "Server sedang tidur. Pertanyaan pertama bisa makan waktu sekitar 1 menit.",
      };
    }
    return {
      state: "down",
      stage,
      message: `Server backend sedang bermasalah (${stage ?? "status tidak diketahui"}). Coba lagi nanti.`,
    };
  } catch {
    return { state: "unknown", stage: null, message: "Status server tidak bisa dicek" };
  }
}
