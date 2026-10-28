import { Activity, AlertTriangle, Compass, Loader2, ShieldAlert } from "lucide-react";
import { Children, isValidElement, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { CitationList } from "@/components/chat/Citations";
import { Badge, CopyButton, IconButton } from "@/components/ui/primitives";
import type { ChatMessage } from "@/hooks/useChat";
import { cn } from "@/lib/utils";

const OUTCOME = {
  answered: null,
  insufficient_evidence: { tone: "warning" as const, label: "Insufficient evidence — abstained" },
  abstained: { tone: "warning" as const, label: "Abstained" },
  failed: { tone: "danger" as const, label: "Failed" },
};

/** Turn "[S1]" markers in rendered text into small links to the citation cards. */
function withCitationLinks(children: ReactNode): ReactNode {
  return Children.map(children, (child) => {
    if (typeof child !== "string") return isValidElement(child) ? child : child;
    const parts = child.split(/(\[S\d+\])/g);
    return parts.map((part, i) => {
      const m = /^\[(S\d+)\]$/.exec(part);
      if (!m) return part;
      return (
        <a key={i} href={`#cite-${m[1]}`} className="mx-0.5 rounded bg-accent px-1 align-baseline font-mono text-[10.5px] font-semibold text-primary no-underline hover:underline"
           onClick={(e) => {
             e.preventDefault();
             const el = document.getElementById(`cite-${m[1]}`) as HTMLDetailsElement | null;
             if (el) { el.open = true; el.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
           }}>
          {m[1]}
        </a>
      );
    });
  });
}

export function MessageItem({ message, onInspect, selected }: { message: ChatMessage; onInspect: (requestId: string) => void; selected: boolean }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-user-bubble px-4 py-2.5 text-[15px] leading-relaxed">{message.content}</div>
      </div>
    );
  }
  const r = message.result;
  const outcome = r ? OUTCOME[r.outcome] : null;
  const streaming = message.status === "streaming";
  return (
    <div className={cn("group flex gap-3", selected && "rounded-xl bg-accent/40 -mx-2 px-2 py-1")}>
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-card" aria-hidden>
        <Compass className="h-4 w-4 text-primary" />
      </div>
      <div className="min-w-0 flex-1">
        {outcome && <Badge tone={outcome.tone} className="mb-1.5"><ShieldAlert className="h-3 w-3" /> {outcome.label}</Badge>}
        {message.content ? (
          <div className="prose-answer text-[15px]">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
              p: ({ children }) => <p>{withCitationLinks(children)}</p>,
              li: ({ children }) => <li>{withCitationLinks(children)}</li>,
              a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer noopener" className="text-primary underline">{children}</a>,
            }}>
              {message.content}
            </ReactMarkdown>
          </div>
        ) : streaming ? (
          <p className="inline-flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Retrieving evidence and generating…</p>
        ) : null}
        {streaming && message.content && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-foreground/60 align-middle" aria-hidden />}
        {message.status === "error" && (
          <p className="mt-1 flex items-start gap-1.5 rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {message.error}
          </p>
        )}
        {message.status === "cancelled" && <p className="mt-1 text-xs text-muted-foreground">Generation stopped.</p>}
        {r?.guard_notes.map((n) => <p key={n} className="mt-1.5 text-xs text-warning">⚠ {n}</p>)}
        {r && <CitationList citations={r.citations} report={r.citation_report} answered={r.outcome === "answered"} />}
        <div className="mt-1.5 flex items-center gap-0.5 opacity-70 transition-opacity group-hover:opacity-100">
          {message.content && !streaming && <CopyButton text={message.content} label="Copy answer" />}
          {message.requestId && (
            <IconButton label="Inspect execution trace" onClick={() => onInspect(message.requestId!)}>
              <Activity className="h-3.5 w-3.5" />
            </IconButton>
          )}
          {r?.model && <span className="ml-1 text-[11px] text-muted-foreground">{r.model}</span>}
        </div>
      </div>
    </div>
  );
}
