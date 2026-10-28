import type {
  DocumentSummary, ExecutionTrace, Health, OllamaModel, OllamaStatus, PipelineConfig, PipelineEvent, Preset, Registry,
  ValidationResult,
} from "@/types/api";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly detail?: unknown) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; errors?: { message: string }[] };
    if (d.errors?.length) return `${d.message ?? "Invalid request"}: ${d.errors.map((e) => e.message).join("; ")}`;
    if (d.message) return d.message;
  }
  return "Request failed";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  } catch {
    throw new ApiError("Cannot reach the HYU Compass API. Is the backend running on port 8000?", 0);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(describe(body.detail), res.status, body.detail);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/api/v1/health"),
  registry: () => request<Registry>("/api/v1/pipeline/registry"),
  config: () => request<{ config: PipelineConfig; active_index_config: PipelineConfig["stages"] | null }>("/api/v1/pipeline/config"),
  validate: (config: PipelineConfig) => post<ValidationResult>("/api/v1/pipeline/config/validate", config),
  presets: () => request<Preset[]>("/api/v1/pipeline/presets"),
  savePreset: (name: string, description: string, config: PipelineConfig) =>
    post<Preset>("/api/v1/pipeline/presets", { name, description, config }),
  ollamaStatus: () => request<OllamaStatus>("/api/v1/ollama/status"),
  ollamaModels: () => request<{ models: OllamaModel[]; default: string | null }>("/api/v1/ollama/models"),
  ollamaShow: (model: string) =>
    request<{ capabilities: string[]; context_length: number | null; details: Record<string, unknown> }>(
      `/api/v1/ollama/show?model=${encodeURIComponent(model)}`,
    ),
  trace: (requestId: string) => request<ExecutionTrace>(`/api/v1/traces/${requestId}`),
  documents: () => request<{ revision_id: string; documents: DocumentSummary[] }>("/api/v1/documents"),
  ingestLocal: (path: string, config: PipelineConfig) =>
    post<Record<string, unknown>>("/api/v1/ingest/local", { path, config, activate: true }),
};

/** Parse a text/event-stream body into events. Exported for tests. */
export function parseSseChunk(buffer: string): { events: PipelineEvent[]; rest: string } {
  const events: PipelineEvent[] = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    const data = block
      .split("\n")
      .filter((line) => line.startsWith("data: "))
      .map((line) => line.slice(6))
      .join("\n");
    if (data) events.push(JSON.parse(data) as PipelineEvent);
  }
  return { events, rest };
}

/**
 * POST /chat/stream and dispatch each SSE event. Uses fetch (not EventSource) because the
 * request carries a JSON body with the configuration snapshot.
 */
export async function streamChat(
  body: { question: string; session_id: string; config: PipelineConfig },
  onEvent: (event: PipelineEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/v1/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (signal.aborted) throw err;
    throw new ApiError("Cannot reach the HYU Compass API. Is the backend running on port 8000?", 0);
  }
  if (!res.ok || !res.body) {
    const payload = await res.json().catch(() => ({}));
    throw new ApiError(describe(payload.detail), res.status, payload.detail);
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    const parsed = parseSseChunk(buffer + value);
    buffer = parsed.rest;
    parsed.events.forEach(onEvent);
  }
}
