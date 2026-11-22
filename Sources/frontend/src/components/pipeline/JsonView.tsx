// Collapsible, copyable JSON viewer for stage inputs/outputs. Long strings are clipped with
// an explicit "show all" so large traces stay readable.
import { ChevronRight } from "lucide-react";
import { useState } from "react";

import { CopyButton } from "@/components/ui/primitives";

const CLIP = 240;

export function JsonView({ value, label }: { value: unknown; label?: string }) {
  const empty = value == null || (typeof value === "object" && Object.keys(value as object).length === 0);
  return (
    <div className="relative rounded-lg border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-2 py-1">
        <span className="text-[11px] font-medium text-muted-foreground">{label ?? "JSON"}</span>
        {!empty && <CopyButton text={JSON.stringify(value, null, 2)} label="Copy JSON" />}
      </div>
      <div className="max-h-96 overflow-auto px-2 py-1.5 font-mono text-[11.5px] leading-relaxed">
        {empty ? <span className="text-muted-foreground">(empty)</span> : <Node value={value} depth={0} />}
      </div>
    </div>
  );
}

function Node({ name, value, depth }: { name?: string; value: unknown; depth: number }) {
  const keyEl = name !== undefined ? <span className="text-info">{name}: </span> : null;
  if (value !== null && typeof value === "object") {
    const entries = Array.isArray(value) ? value.map((v, i) => [String(i), v] as const) : Object.entries(value as Record<string, unknown>);
    const summary = Array.isArray(value) ? `[${value.length}]` : `{${entries.length}}`;
    return (
      <details open={depth < 1 || entries.length <= 4} className="group">
        <summary className="flex list-none items-center gap-0.5 [&::-webkit-details-marker]:hidden">
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden />
          {keyEl}
          <span className="text-muted-foreground">{summary}</span>
        </summary>
        <div className="ml-3 border-l border-border pl-2">
          {entries.map(([k, v]) => <Node key={k} name={k} value={v} depth={depth + 1} />)}
        </div>
      </details>
    );
  }
  return (
    <div className="ml-3.5">
      {keyEl}
      <Scalar value={value} />
    </div>
  );
}

function Scalar({ value }: { value: unknown }) {
  const [full, setFull] = useState(false);
  if (typeof value === "string") {
    const clipped = !full && value.length > CLIP;
    return (
      <span className="whitespace-pre-wrap break-words text-success">
        "{clipped ? value.slice(0, CLIP) + "…" : value}"
        {value.length > CLIP && (
          <button type="button" className="ml-1 text-[10px] text-primary underline" onClick={() => setFull(!full)}>
            {full ? "show less" : `show all (${value.length} chars)`}
          </button>
        )}
      </span>
    );
  }
  if (typeof value === "number") return <span className="text-warning">{value}</span>;
  if (typeof value === "boolean") return <span className="text-primary">{String(value)}</span>;
  return <span className="text-muted-foreground">null</span>;
}
