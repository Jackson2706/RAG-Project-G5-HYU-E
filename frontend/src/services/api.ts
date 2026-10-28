// Every call the frontend makes to FastAPI (backend/app/api.py).
import type { ConfigError, Health, IndexInfo, OllamaModel, StageChoices, StageDef, StreamEvent, Trace } from "@/types/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  } catch {
    throw new Error("Cannot reach the backend. Is it running on http://127.0.0.1:8000?");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(errorText(body.detail, res.status));
  return body as T;
}

/** FastAPI errors are a string, or {message, errors: [...]} for an invalid configuration. */
function errorText(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  const d = detail as { errors?: ConfigError[] } | undefined;
  if (d?.errors?.length) return d.errors.map((e) => e.message).join("; ");
  return `Request failed (${status})`;
}

const post = <T>(path: string, data: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(data) });

export const api = {
  health: () => request<Health>("/api/health"),
  registry: () => request<{ stages: StageDef[] }>("/api/pipeline/registry"),
  validate: (stages: StageChoices) => post<{ valid: boolean; errors: ConfigError[] }>("/api/pipeline/config/validate", stages),
  models: () => request<{ models: OllamaModel[]; default: string | null }>("/api/ollama/models"),
  ingest: (folder: string, stages: StageChoices) =>
    post<{ documents: number; chunks: number; errors: string[] } & Partial<IndexInfo>>("/api/ingest", { folder, stages }),
  trace: (requestId: string) => request<Trace>(`/api/traces/${requestId}`),
};

/** Split received text into complete SSE events ("data: {...}\n\n"); return the unfinished rest. */
export function parseEvents(buffer: string): { events: StreamEvent[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events = parts.filter((p) => p.startsWith("data: ")).map((p) => JSON.parse(p.slice(6)) as StreamEvent);
  return { events, rest };
}

/**
 * Ask a question and receive live events. We use fetch() instead of EventSource because we
 * need to POST the question and the chosen methods in the request body.
 */
export async function streamChat(question: string, stages: StageChoices, onEvent: (e: StreamEvent) => void, signal: AbortSignal) {
  let res: Response;
  try {
    res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, stages }),
      signal,
    });
  } catch (err) {
    if (signal.aborted) throw err;
    throw new Error("Cannot reach the backend. Is it running on http://127.0.0.1:8000?");
  }
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    throw new Error(errorText(body.detail, res.status));
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    const parsed = parseEvents(buffer + value);
    buffer = parsed.rest;
    parsed.events.forEach(onEvent);
  }
}
