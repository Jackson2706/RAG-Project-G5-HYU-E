import { CheckCircle2, ChevronRight, Circle, Loader2, MinusCircle, XCircle } from "lucide-react";
import { useState } from "react";

import { JsonView } from "@/components/pipeline/JsonView";
import { Badge, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/primitives";
import { cn, formatMs } from "@/lib/utils";
import type { StageDef, StageRecord } from "@/types/api";

const STATUS = {
  waiting: { icon: Circle, cls: "text-muted-foreground", label: "Not run yet" },
  running: { icon: Loader2, cls: "text-info animate-spin", label: "Running" },
  completed: { icon: CheckCircle2, cls: "text-success", label: "Completed" },
  skipped: { icon: MinusCircle, cls: "text-warning", label: "Skipped" },
  failed: { icon: XCircle, cls: "text-danger", label: "Failed" },
};

type Row = Record<string, unknown>;

/** Readable cards for lists of retrieved chunks (candidate retrieval, postfiltering and Metadata Enrichment outputs). */
function ChunkList({ items }: { items: Row[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <ol className="space-y-1.5">
      {items.map((c, i) => (
        <li key={String(c.chunk_id) + i} className="rounded-lg border border-border bg-card p-2 text-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-muted-foreground">#{String(c.rank ?? i + 1)}</span>
            <span className="min-w-0 flex-1 truncate font-medium">{String(c.title ?? `doc ${String(c.doc_id).slice(0, 8)}`)}</span>
            {typeof c.score === "number" && <Badge tone="info">similarity {c.score.toFixed(4)}</Badge>}
          </div>
          <p className="mt-0.5 font-mono text-[10.5px] text-muted-foreground">
            chunk {String(c.chunk_id).slice(0, 8)}{c.section ? ` · § ${String(c.section)}` : ""}{c.page_number ? ` · page ${String(c.page_number)}` : ""}
          </p>
          {typeof c.text === "string" && (
            <>
              <p className={cn("mt-1 whitespace-pre-wrap leading-snug", open !== i && "line-clamp-3")}>{c.text}</p>
              <button type="button" className="text-[10.5px] text-primary underline" onClick={() => setOpen(open === i ? null : i)}>
                {open === i ? "collapse" : "expand"}
              </button>
            </>
          )}
        </li>
      ))}
    </ol>
  );
}

const isChunkList = (v: unknown): v is Row[] => Array.isArray(v) && v.length > 0 && typeof v[0] === "object" && v[0] !== null && "chunk_id" in v[0];

/** Show the real output: chunk lists as cards, the answer as text, everything else as JSON. */
function Output({ output }: { output: unknown }) {
  if (output == null) return <p className="text-xs text-muted-foreground">No output.</p>;
  if (isChunkList(output)) return <ChunkList items={output} />;
  if (typeof output !== "object" || Array.isArray(output)) return <JsonView value={output} label="Output" />;
  const obj = output as Row;
  const listKey = (["candidates", "kept", "evidence"] as const).find((k) => isChunkList(obj[k]));
  const rest = Object.fromEntries(Object.entries(obj).filter(([k]) => k !== listKey));
  return (
    <div className="space-y-2">
      {typeof obj.answer === "string" && <div className="whitespace-pre-wrap rounded-lg border border-border bg-card p-2 text-xs">{obj.answer}</div>}
      {listKey === "candidates" && (
        <p className="text-[11px] text-muted-foreground">Qdrant stores only IDs and vectors. The chunk text is loaded from MongoDB in Metadata Enrichment.</p>
      )}
      {listKey && <ChunkList items={obj[listKey] as Row[]} />}
      {Object.keys(rest).length > 0 && <JsonView value={rest} label="Output" />}
    </div>
  );
}

/** One stage with an implemented method, in the Execution tab. Expandable once it has run. */
export function StageTraceCard({ stage, record }: { stage: StageDef; record?: StageRecord }) {
  const status = STATUS[record?.status ?? "waiting"];
  const Icon = status.icon;
  const expandable = !!record && record.status !== "skipped"; // a skipped stage has no input/output to show
  return (
    <details className="group rounded-xl border border-border bg-card" data-testid={`stage-${stage.stage_id}`} data-status={record?.status ?? "waiting"}>
      <summary className={cn("flex list-none items-center gap-2 px-3 py-2 [&::-webkit-details-marker]:hidden", !expandable && "pointer-events-none")}>
        <ChevronRight className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90", !expandable && "invisible")} aria-hidden />
        <Icon className={cn("h-4 w-4 shrink-0", status.cls)} aria-label={status.label} />
        <div className="min-w-0 flex-1">
          <p className={cn("truncate text-sm font-medium", !record && "text-muted-foreground")}>
            {stage.name}{record?.method_name && <span className="font-normal text-muted-foreground"> · {record.method_name}</span>}
          </p>
          <p className="truncate text-[11px] text-muted-foreground">{record ? record.error ?? record.summary : stage.description}</p>
        </div>
        {expandable && record.status !== "running" && <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{formatMs(record.duration_ms)}</span>}
      </summary>
      {expandable && (
        <div className="border-t border-border p-3">
          <p className="mb-2 text-xs">
            <span className={status.cls.replace("animate-spin", "")}>{status.label}</span> · {formatMs(record.duration_ms)} (measured) ·{" "}
            <span className="font-mono">{record.method_id}</span>
          </p>
          {record.error && <p role="alert" className="mb-2 rounded-md bg-danger/10 px-2 py-1.5 text-xs text-danger">{record.error}</p>}
          <Tabs defaultValue="output">
            <TabsList>
              <TabsTrigger value="input">Input</TabsTrigger>
              <TabsTrigger value="output">Output</TabsTrigger>
              <TabsTrigger value="params">Parameters</TabsTrigger>
            </TabsList>
            <TabsContent value="input" className="mt-2"><JsonView value={record.input} label="Input" /></TabsContent>
            <TabsContent value="output" className="mt-2"><Output output={record.output} /></TabsContent>
            <TabsContent value="params" className="mt-2"><JsonView value={record.params} label="Parameters used" /></TabsContent>
          </Tabs>
        </div>
      )}
    </details>
  );
}
