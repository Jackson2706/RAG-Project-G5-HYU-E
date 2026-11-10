import { ChevronDown, FileText } from "lucide-react";

import { Badge } from "@/components/ui/primitives";
import type { SourceReference } from "@/types/api";

function SourceCard({ c }: { c: SourceReference }) {
  const where = [c.section, c.page_number ? `page ${c.page_number}` : null].filter(Boolean).join(" · ");
  return (
    <details className="group rounded-lg border border-border bg-card text-xs" id={`source-${c.label}`}>
      <summary className="flex list-none items-start gap-2 p-2 [&::-webkit-details-marker]:hidden">
        <span className="mt-0.5 rounded bg-primary px-1.5 py-0.5 font-mono text-[10.5px] font-semibold text-primary-foreground">{c.label}</span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1 truncate font-medium"><FileText className="h-3 w-3 shrink-0 text-muted-foreground" />{c.title}</p>
          {where && <p className="truncate text-[11px] text-muted-foreground">{where}</p>}
        </div>
        <Badge tone="info">similarity {c.score.toFixed(3)}</Badge>
        <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="space-y-1.5 border-t border-border p-2">
        <blockquote className="whitespace-pre-wrap border-l-2 border-primary/50 pl-2 leading-snug">{c.excerpt}</blockquote>
        <p className="font-mono text-[10.5px] text-muted-foreground">{c.source_uri} · chunk {c.chunk_id.slice(0, 8)}</p>
      </div>
    </details>
  );
}

/**
 * Source references: the evidence the answer refers to ([E1], …), plus (collapsed) evidence that was
 * retrieved but not referred to. This shows where text came from; it does not verify the claims.
 */
export function Sources({ sources }: { sources: SourceReference[] }) {
  const cited = sources.filter((c) => c.cited);
  const other = sources.filter((c) => !c.cited);
  if (!sources.length) return null;
  return (
    <div className="mt-3 space-y-1.5">
      {cited.length > 0 && <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Sources</h4>}
      {cited.map((c) => <SourceCard key={c.label} c={c} />)}
      {other.length > 0 && (
        <details className="group">
          <summary className="flex list-none items-center gap-1 text-[11px] text-muted-foreground [&::-webkit-details-marker]:hidden">
            <ChevronDown className="h-3 w-3 transition-transform group-open:rotate-180" /> {other.length} retrieved but not cited
          </summary>
          <div className="mt-1.5 space-y-1.5">{other.map((c) => <SourceCard key={c.label} c={c} />)}</div>
        </details>
      )}
    </div>
  );
}
