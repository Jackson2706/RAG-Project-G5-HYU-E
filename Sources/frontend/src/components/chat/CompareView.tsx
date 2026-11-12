// Compare mode (AGENTS.md "UI and demo rules"): pick 2-4 presets, run one question through each in turn,
// and show the answers side by side. Clicking a column opens that run's Execution trace.
import { Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ActionBadge } from "@/components/chat/MessageItem";
import { Badge } from "@/components/ui/primitives";
import type { CompareRun } from "@/hooks/useChat";
import { formatMs } from "@/lib/utils";
import type { Preset } from "@/types/api";

export const MAX_COMPARE = 4;

export function ComparePicker({ presets, chosen, onChange }: { presets: Preset[]; chosen: string[]; onChange: (ids: string[]) => void }) {
  const runnable = presets.filter((p) => p.enabled && p.config);
  const toggle = (id: string) => onChange(chosen.includes(id) ? chosen.filter((c) => c !== id) : [...chosen, id]);
  return (
    <fieldset className="border-b border-border px-3 py-2 text-sm" data-testid="compare-picker">
      <legend className="sr-only">Presets to compare</legend>
      <p className="mb-1.5 text-xs text-muted-foreground">
        Choose 2–{MAX_COMPARE} presets. Each question runs through them one after another. {chosen.length} selected.
      </p>
      <div className="flex max-h-40 flex-wrap gap-1.5 overflow-y-auto">
        {runnable.map((p) => {
          const on = chosen.includes(p.id);
          return (
            <label key={p.id} title={p.description}
                   className={`flex cursor-pointer items-center gap-1.5 rounded-lg border px-2 py-1 text-xs ${on ? "border-primary bg-accent" : "border-border"}`}>
              <input type="checkbox" checked={on} disabled={!on && chosen.length >= MAX_COMPARE} onChange={() => toggle(p.id)} />
              {p.name}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export function CompareColumns({ runs, onInspect }: { runs: CompareRun[]; onInspect: (requestId: string) => void }) {
  const cols = runs.length >= 4 ? "lg:grid-cols-4" : runs.length === 3 ? "lg:grid-cols-3" : "";
  return (
    <div className={`grid gap-3 sm:grid-cols-2 ${cols}`} data-testid="compare-columns">
      {runs.map((run) => (
        <section key={run.presetId} aria-label={run.name}
                 className="flex min-w-0 flex-col rounded-xl border border-border bg-card p-3 text-sm">
          <button type="button" disabled={!run.requestId} onClick={() => run.requestId && onInspect(run.requestId)}
                  className="mb-2 flex items-baseline justify-between gap-2 text-left font-semibold hover:underline disabled:no-underline"
                  title="Show this run's execution trace">
            <span className="truncate">{run.name}</span>
            <span className="shrink-0 text-[11px] font-normal text-muted-foreground">{formatMs(run.trace?.total_ms)}</span>
          </button>
          {run.trace?.action && <ActionBadge action={run.trace.action} />}
          {run.status === "queued" && <p className="text-xs text-muted-foreground">Waiting for the previous preset…</p>}
          {run.status === "streaming" && !run.content && (
            <p className="inline-flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Running…</p>
          )}
          {run.content && <div className="prose-answer text-[13.5px]"><ReactMarkdown remarkPlugins={[remarkGfm]}>{run.content}</ReactMarkdown></div>}
          {run.status === "error" && <p role="alert" className="mt-1 text-xs text-danger">{run.error}</p>}
          {run.status === "cancelled" && <p className="mt-1 text-xs text-muted-foreground">Stopped.</p>}
          {run.trace && (
            <div className="mt-2 flex flex-wrap gap-1">
              {run.trace.sources.some((s) => s.cited)
                ? run.trace.sources.filter((s) => s.cited).map((s) => (
                    <a key={s.chunk_id} href={s.source_uri} target="_blank" rel="noreferrer" title={s.title} className="max-w-full">
                      <Badge className="max-w-full truncate">{`${s.label} ${s.title}`}</Badge>
                    </a>))
                : <span className="text-[11px] text-muted-foreground">No citations</span>}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
