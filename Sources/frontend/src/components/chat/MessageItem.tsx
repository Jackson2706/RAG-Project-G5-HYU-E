import { Activity, AlertTriangle, Compass, Loader2 } from "lucide-react";
import { Children, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Sources } from "@/components/chat/Sources";
import { Badge, CopyButton, IconButton } from "@/components/ui/primitives";
import type { ChatMessage } from "@/hooks/useChat";

/** Make "[E1]" in the answer a small link that opens the matching source card. */
function linkSources(children: ReactNode): ReactNode {
  return Children.map(children, (child) =>
    typeof child !== "string"
      ? child
      : child.split(/(\[E\d+\])/g).map((part, i) => {
          const label = /^\[(E\d+)\]$/.exec(part)?.[1];
          if (!label) return part;
          return (
            <a key={i} href={`#source-${label}`} className="mx-0.5 rounded bg-accent px-1 font-mono text-[10.5px] font-semibold text-primary no-underline"
               onClick={(e) => {
                 e.preventDefault();
                 const card = document.getElementById(`source-${label}`) as HTMLDetailsElement | null;
                 if (card) { card.open = true; card.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
               }}>
              {label}
            </a>
          );
        }),
  );
}

export function MessageItem({ message, onInspect }: { message: ChatMessage; onInspect: (requestId: string) => void }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-user-bubble px-4 py-2.5 text-[15px] leading-relaxed">{message.content}</div>
      </div>
    );
  }
  const streaming = message.status === "streaming";
  const trace = message.trace;
  return (
    <div className="group flex gap-3">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-card" aria-hidden>
        <Compass className="h-4 w-4 text-primary" />
      </div>
      <div className="min-w-0 flex-1">
        {trace?.outcome === "insufficient_context" && <Badge tone="warning" className="mb-1.5">Not enough evidence</Badge>}
        {message.content ? (
          <div className="prose-answer text-[15px]">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
              p: ({ children }) => <p>{linkSources(children)}</p>,
              li: ({ children }) => <li>{linkSources(children)}</li>,
            }}>{message.content}</ReactMarkdown>
          </div>
        ) : streaming ? (
          <p className="inline-flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Searching documents…</p>
        ) : null}
        {message.status === "error" && (
          <p role="alert" className="mt-1 flex items-start gap-1.5 rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {message.error}
          </p>
        )}
        {message.status === "cancelled" && <p className="mt-1 text-xs text-muted-foreground">Stopped.</p>}
        {trace && <Sources sources={trace.sources} />}
        <div className="mt-1.5 flex items-center gap-0.5 opacity-70 transition-opacity group-hover:opacity-100">
          {message.content && !streaming && <CopyButton text={message.content} label="Copy answer" />}
          {message.requestId && (
            <IconButton label="Show execution trace" onClick={() => onInspect(message.requestId!)}><Activity className="h-3.5 w-3.5" /></IconButton>
          )}
          {trace?.model && <span className="ml-1 text-[11px] text-muted-foreground">{trace.model}</span>}
        </div>
      </div>
    </div>
  );
}
