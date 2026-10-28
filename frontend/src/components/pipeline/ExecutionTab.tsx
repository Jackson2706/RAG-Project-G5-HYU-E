import { Activity } from "lucide-react";

import { StageTraceCard, type ChunkLookup } from "@/components/pipeline/StageTraceCard";
import { Badge, CopyButton } from "@/components/ui/primitives";
import type { ChatState } from "@/hooks/useChat";
import { methodOf, stageById } from "@/lib/config";
import { formatMs } from "@/lib/utils";
import type { Registry } from "@/types/api";

export function ExecutionTab({ registry, chat }: { registry: Registry; chat: ChatState }) {
  const stages = stageById(registry);
  const requests = chat.active.messages.filter((m) => m.role === "assistant" && m.requestId);
  const rid = chat.selectedRequestId;
  const live = rid ? chat.traces[rid] : undefined;

  if (!requests.length && !live) {
    return (
      <div className="flex flex-col items-center gap-2 p-10 text-center text-sm text-muted-foreground">
        <Activity className="h-6 w-6" />
        <p>Ask a question to see every stage’s real input, output, parameters and timing.</p>
      </div>
    );
  }

  const final = live?.trace;
  const lookup: ChunkLookup = {};
  for (const id of ["lexical_retrieval", "metadata_enrichment"]) {
    const cands = live?.stages[id]?.output?.candidates;
    if (Array.isArray(cands)) for (const c of cands as Record<string, unknown>[]) if (c.text) lookup[String(c.chunk_id)] = c;
  }
  const statusTone = live?.status === "completed" ? "success" : live?.status === "failed" ? "danger" : live?.status === "cancelled" ? "warning" : "info";
  const counts = live ? Object.values(live.stages).reduce<Record<string, number>>((acc, s) => ({ ...acc, [s.status]: (acc[s.status] ?? 0) + 1 }), {}) : {};

  return (
    <div className="space-y-3 p-3">
      <div className="space-y-2 rounded-xl border border-border bg-surface p-3">
        <label htmlFor="request-select" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Request</label>
        <select id="request-select" className="h-8 w-full rounded-md border border-border bg-card px-2 text-sm" value={rid ?? ""}
                onChange={(e) => void chat.selectRequest(e.target.value)}>
          {!rid && <option value="">Select a request…</option>}
          {requests.map((m, i) => {
            const question = chat.active.messages[chat.active.messages.indexOf(m) - 1]?.content ?? "";
            return <option key={m.requestId} value={m.requestId}>{`#${i + 1} ${question.slice(0, 70)}`}</option>;
          })}
        </select>
        {live && (
          <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
            <Badge tone={statusTone}>{live.status}</Badge>
            {final?.total_ms != null && <Badge>total {formatMs(final.total_ms)}</Badge>}
            {Object.entries(counts).map(([k, v]) => <Badge key={k}>{v} {k}</Badge>)}
            {live.config_hash && <Badge tone="primary">config {live.config_hash}</Badge>}
            {typeof live.index_revision?.revision_id === "string" && <Badge>index {live.index_revision.revision_id}</Badge>}
            <span className="ml-auto inline-flex items-center gap-1 font-mono text-muted-foreground">
              {live.request_id.slice(0, 12)} <CopyButton text={live.request_id} label="Copy request ID" />
            </span>
          </div>
        )}
        {final?.error && <p className="text-xs text-danger" role="alert">{final.error}</p>}
      </div>

      {live ? (
        <ol className="space-y-1.5" aria-label="Pipeline stages">
          {registry.online_order.map((id, i) => {
            const t = live.stages[id];
            const methodId = t?.method_id ?? final?.config.stages[id]?.method;
            return (
              <li key={id}>
                <StageTraceCard spec={stages[id]} trace={t} index={i + 1} lookup={lookup} methodName={methodOf(stages[id], methodId)?.display_name} />
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="p-4 text-center text-xs text-muted-foreground">Trace not available (it may not have been stored).</p>
      )}
    </div>
  );
}
