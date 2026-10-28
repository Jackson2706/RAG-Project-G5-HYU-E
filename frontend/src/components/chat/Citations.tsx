import { CheckCircle2, ChevronDown, FileText, HelpCircle, XCircle } from "lucide-react";

import { Badge, Tooltip } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import type { Citation, CitationReport } from "@/types/api";

function location(c: Citation): string {
  const section = c.section_path.filter((s) => s !== c.title).join(" › ");
  return [section, c.page_number ? `page ${c.page_number}` : null].filter(Boolean).join(" · ");
}

function SpanBadge({ c }: { c: Citation }) {
  if (!c.resolved) return <Badge tone="danger"><XCircle className="h-3 w-3" /> unresolved</Badge>;
  if (c.span_verified === true)
    return (
      <Tooltip content="The stored character span re-reads to exactly this chunk text. This checks the source location, not whether the claim is true.">
        <span><Badge tone="success"><CheckCircle2 className="h-3 w-3" aria-label="span verified" /><span className="hidden sm:inline">span verified</span></Badge></span>
      </Tooltip>
    );
  if (c.span_verified === false) return <Badge tone="danger"><XCircle className="h-3 w-3" /> span mismatch</Badge>;
  return <Badge><HelpCircle className="h-3 w-3" /> span not checked</Badge>;
}

export function CitationCard({ c }: { c: Citation }) {
  return (
    <details className="group rounded-lg border border-border bg-card text-xs" id={`cite-${c.marker}`}>
      <summary className="flex list-none items-start gap-2 p-2 [&::-webkit-details-marker]:hidden">
        <span className={cn("mt-0.5 rounded px-1.5 py-0.5 font-mono text-[10.5px] font-semibold", c.cited ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>{c.marker}</span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1 truncate font-medium"><FileText className="h-3 w-3 shrink-0 text-muted-foreground" />{c.title ?? c.doc_id}</p>
          {location(c) && <p className="truncate text-[11px] text-muted-foreground">{location(c)}</p>}
        </div>
        <SpanBadge c={c} />
        <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="space-y-1.5 border-t border-border p-2">
        <blockquote className="whitespace-pre-wrap border-l-2 border-primary/50 pl-2 text-[11.5px] leading-snug">{c.excerpt}</blockquote>
        <dl className="grid grid-cols-[auto_1fr] gap-x-2 font-mono text-[10.5px] text-muted-foreground">
          <dt>source</dt><dd className="truncate">{c.source_uri}</dd>
          <dt>doc_id</dt><dd className="truncate">{c.doc_id}</dd>
          <dt>chunk_id</dt><dd className="truncate">{c.chunk_id}</dd>
          {c.source_span && (<><dt>span</dt><dd>{c.source_span.start}–{c.source_span.end}</dd></>)}
        </dl>
      </div>
    </details>
  );
}

export function CitationList({ citations, report, answered }: { citations: Citation[]; report: CitationReport | null; answered: boolean }) {
  const cited = citations.filter((c) => c.cited);
  const uncited = citations.filter((c) => !c.cited);
  if (!citations.length) return null;
  return (
    <div className="mt-3 space-y-2">
      {cited.length > 0 && (
        <section aria-label="Sources cited in the answer" className="space-y-1.5">
          <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Cited sources</h4>
          {cited.map((c) => <CitationCard key={c.marker} c={c} />)}
        </section>
      )}
      {uncited.length > 0 && (
        <details className="group">
          <summary className="flex list-none items-center gap-1 text-[11px] text-muted-foreground [&::-webkit-details-marker]:hidden">
            <ChevronDown className="h-3 w-3 transition-transform group-open:rotate-180" />
            {answered ? `${uncited.length} retrieved but not cited (relevant ≠ supporting)` : `${uncited.length} retrieved passages (none supported an answer)`}
          </summary>
          <div className="mt-1.5 space-y-1.5">{uncited.map((c) => <CitationCard key={c.marker} c={c} />)}</div>
        </details>
      )}
      {report && answered && (
        <p className="text-[10.5px] text-muted-foreground">
          {report.sentences_with_citation}/{report.sentences_total} sentences carry a citation · {report.note}
        </p>
      )}
    </div>
  );
}
