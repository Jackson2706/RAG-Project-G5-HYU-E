import { Ban, CheckCircle2, ChevronRight, Circle, Loader2, SkipForward, XCircle } from "lucide-react";
import { useState } from "react";

import { JsonView } from "@/components/pipeline/JsonView";
import { Badge, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/primitives";
import { cn, formatMs } from "@/lib/utils";
import type { StageSpec, StageStatus, StageTrace } from "@/types/api";

export const STAGE_STATUS: Record<StageStatus, { icon: typeof Circle; cls: string; label: string }> = {
  pending: { icon: Circle, cls: "text-muted-foreground", label: "Pending" },
  running: { icon: Loader2, cls: "text-info animate-spin", label: "Running" },
  completed: { icon: CheckCircle2, cls: "text-success", label: "Completed" },
  bypassed: { icon: SkipForward, cls: "text-warning", label: "Bypassed" },
  failed: { icon: XCircle, cls: "text-danger", label: "Failed" },
};

type Row = Record<string, unknown>;
/** chunk_id → title/text/section/page reported by another stage of the same request. */
export type ChunkLookup = Record<string, Row>;

/** Readable list for candidate/evidence arrays (chunk_id + scores + text). */
function CandidateList({ items: raw, title, lookup }: { items: Row[]; title: string; lookup: ChunkLookup }) {
  // Retrieval stages carry only IDs and scores (Qdrant payloads hold no text); join the text
  // that Metadata Enrichment loaded from MongoDB for the same chunk_id in this request.
  const items = raw.map((c) => {
    const extra = lookup[String(c.chunk_id)];
    return extra && c.text === undefined ? { ...c, title: extra.title, text: extra.text, section: extra.section, page: extra.page, _joined: true } : c;
  });
  const [expanded, setExpanded] = useState<string | null>(null);
  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-medium text-muted-foreground">{title} ({items.length})</p>
      <ol className="space-y-1.5">
        {items.map((c, i) => {
          const id = String(c.chunk_id ?? i);
          const text = typeof c.text === "string" ? c.text : null;
          const scores = (["dense_score", "lexical_score", "fused_score"] as const).filter((k) => typeof c[k] === "number");
          return (
            <li key={id + i} className="rounded-lg border border-border bg-card p-2 text-xs">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-mono text-[11px] text-muted-foreground">#{i + 1}</span>
                <span className="min-w-0 flex-1 truncate font-medium">{String(c.title ?? c.doc_id ?? "")}</span>
                {scores.map((k) => (
                  <Badge key={k} tone={k === "dense_score" ? "info" : k === "lexical_score" ? "warning" : "primary"}>
                    {k.replace("_score", "")} {(c[k] as number).toFixed(4)}
                  </Badge>
                ))}
                {typeof c.dense_rank === "number" && typeof c.lexical_rank === "number" && <Badge>ranks d{c.dense_rank as number}/l{c.lexical_rank as number}</Badge>}
              </div>
              <div className="mt-0.5 flex flex-wrap gap-x-2 text-[10.5px] text-muted-foreground">
                <span className="font-mono">chunk {id.slice(0, 8)}</span>
                {c.section ? <span>§ {String(c.section)}</span> : null}
                {c.page ? <span>p. {String(c.page)}</span> : null}
                {c.payload && typeof c.payload === "object" && (c.payload as Row).campus ? <span>campus {String((c.payload as Row).campus)}</span> : null}
              </div>
              {c._joined ? <p className="mt-0.5 text-[10px] italic text-muted-foreground">text from Metadata Enrichment (MongoDB)</p> : null}
              {text && (
                <p className={cn("mt-1 whitespace-pre-wrap text-[11.5px] leading-snug", expanded !== id && "line-clamp-3")}>
                  {text}
                </p>
              )}
              {text && text.length > 160 && (
                <button type="button" className="mt-0.5 text-[10.5px] text-primary underline" onClick={() => setExpanded(expanded === id ? null : id)}>
                  {expanded === id ? "collapse" : "full text"}
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function OutputView({ output, lookup }: { output: Record<string, unknown>; lookup: ChunkLookup }) {
  const lists = (["candidates", "evidence"] as const).filter((k) => Array.isArray(output[k]) && (output[k] as Row[]).length > 0);
  const rest = Object.fromEntries(Object.entries(output).filter(([k]) => !lists.includes(k as (typeof lists)[number])));
  const answer = typeof output.answer === "string" ? output.answer : null;
  return (
    <div className="space-y-2">
      {answer && <div className="whitespace-pre-wrap rounded-lg border border-border bg-card p-2 text-xs">{answer}</div>}
      {lists.map((k) => <CandidateList key={k} items={output[k] as Row[]} lookup={lookup} title={k === "evidence" ? "Selected evidence" : "Candidates"} />)}
      {Object.keys(rest).length > 0 && <JsonView value={rest} label="Output" />}
      {!lists.length && !Object.keys(rest).length && <p className="text-xs text-muted-foreground">No output recorded.</p>}
    </div>
  );
}

export function StageTraceCard({ spec, trace, methodName, index, lookup }: { spec: StageSpec; trace?: StageTrace; methodName?: string; index: number; lookup: ChunkLookup }) {
  const status = trace?.status ?? "pending";
  const disabled = status === "bypassed" && trace?.summary === "Disabled";
  const S = STAGE_STATUS[status];
  const Icon = S.icon;
  const hasDetail = trace && status !== "pending";
  return (
    <details className="group rounded-xl border border-border bg-card" data-testid={`stage-trace-${spec.stage_id}`} data-status={status}>
      <summary className={cn("flex list-none items-center gap-2 px-3 py-2 [&::-webkit-details-marker]:hidden", !hasDetail && "pointer-events-none")}>
        <ChevronRight className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90", !hasDetail && "invisible")} aria-hidden />
        <Icon className={cn("h-4 w-4 shrink-0", S.cls)} aria-label={S.label} />
        <span className="w-4 shrink-0 text-right font-mono text-[10.5px] text-muted-foreground">{index}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={cn("truncate text-sm font-medium", status === "pending" && "text-muted-foreground")}>{spec.stage_name}</span>
            {methodName && status !== "pending" && !disabled && <span className="hidden truncate text-[11px] text-muted-foreground sm:inline">· {methodName}</span>}
          </div>
          {trace?.summary && status !== "pending" && <p className="truncate text-[11px] text-muted-foreground">{trace.error ?? trace.summary}</p>}
        </div>
        <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{status === "running" ? "…" : status === "pending" ? "" : formatMs(trace?.duration_ms)}</span>
      </summary>
      {hasDetail && (
        <div className="border-t border-border p-3">
          <Tabs defaultValue="overview">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="input">Input</TabsTrigger>
              <TabsTrigger value="output">Output</TabsTrigger>
              <TabsTrigger value="debug">Debug</TabsTrigger>
            </TabsList>
            <TabsContent value="overview" className="mt-3 space-y-2 text-xs">
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                <dt className="text-muted-foreground">Status</dt><dd className={S.cls.replace("animate-spin", "")}>{S.label}</dd>
                <dt className="text-muted-foreground">Method</dt><dd>{disabled ? "— (stage disabled)" : <>{methodName ?? trace.method_id} <span className="font-mono text-muted-foreground">({trace.method_id})</span></>}</dd>
                <dt className="text-muted-foreground">Implementation</dt><dd>{trace.implementation_status}</dd>
                <dt className="text-muted-foreground">Duration</dt><dd className="font-mono">{formatMs(trace.duration_ms)} (measured)</dd>
                <dt className="text-muted-foreground">Summary</dt><dd>{trace.summary}</dd>
              </dl>
              {trace.bypass_reason && <p className="rounded-md bg-warning/10 px-2 py-1.5 text-warning"><Ban className="mr-1 inline h-3 w-3" />{trace.bypass_reason}</p>}
              {trace.error && <p className="rounded-md bg-danger/10 px-2 py-1.5 text-danger" role="alert">{trace.error}</p>}
            </TabsContent>
            <TabsContent value="input" className="mt-3"><JsonView value={trace.input} label="Actual input" /></TabsContent>
            <TabsContent value="output" className="mt-3"><OutputView output={trace.output} lookup={lookup} /></TabsContent>
            <TabsContent value="debug" className="mt-3 space-y-2">
              <JsonView value={trace.configuration} label="Applied parameters" />
              <JsonView value={{ request_id: trace.request_id, stage_id: trace.stage_id, method_id: trace.method_id, started_at: trace.started_at,
                                 completed_at: trace.completed_at, error: trace.error, bypass_reason: trace.bypass_reason }} label="Identifiers & timing" />
            </TabsContent>
          </Tabs>
        </div>
      )}
    </details>
  );
}
