import { Compass, Database, Moon, Sun } from "lucide-react";

import { Button, IconButton, Tooltip } from "@/components/ui/primitives";
import type { SystemState } from "@/hooks/useSystem";
import { cn } from "@/lib/utils";

function Dot({ ok, label, detail }: { ok: boolean | undefined; label: string; detail?: string }) {
  return (
    <Tooltip content={detail ?? (ok ? `${label} connected` : `${label} unavailable`)}>
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground" tabIndex={0}>
        <span className={cn("h-2 w-2 rounded-full", ok === undefined ? "bg-border" : ok ? "bg-success" : "bg-danger")} aria-hidden />
        {label}
        <span className="sr-only">{ok ? "connected" : "unavailable"}</span>
      </span>
    </Tooltip>
  );
}

export function Header({ system, dark, onToggleTheme, onOpenIndex, mobileView, onMobileView }: {
  system: SystemState; dark: boolean; onToggleTheme: () => void; onOpenIndex: () => void;
  mobileView: "chat" | "pipeline"; onMobileView: (v: "chat" | "pipeline") => void;
}) {
  const h = system.health;
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-background px-3">
      <div className="flex items-center gap-2">
        <Compass className="h-5 w-5 text-primary" aria-hidden />
        <span className="whitespace-nowrap font-semibold tracking-tight">HYU Compass</span>
        <span className="hidden text-xs text-muted-foreground lg:inline">Evidence-aware RAG for new HYU students</span>
      </div>
      <div className="ml-auto hidden items-center gap-3 md:flex">
        {system.healthError ? (
          <span className="text-xs text-danger">{system.healthError}</span>
        ) : (
          <>
            <Dot ok={h?.mongodb.ok} label="MongoDB" detail={h?.mongodb.error} />
            <Dot ok={h?.qdrant.ok} label="Qdrant" detail={h?.qdrant.error ?? h?.qdrant.mode} />
            <Dot ok={h?.ollama.ok} label="Ollama" detail={h?.ollama.error ?? `Ollama ${h?.ollama.version ?? ""}`} />
            <Dot ok={h ? !!h.active_index : undefined} label="Index" detail={h?.active_index ? `${h.active_index.doc_count} docs · ${h.active_index.chunk_count} chunks · ${h.active_index.revision_id}` : "No active index"} />
          </>
        )}
      </div>
      <div className="ml-auto flex items-center gap-1 md:ml-0">
        <div className="inline-flex rounded-lg bg-muted p-0.5 text-xs md:hidden" role="tablist" aria-label="View">
          {(["chat", "pipeline"] as const).map((v) => (
            <button key={v} type="button" role="tab" aria-selected={mobileView === v} onClick={() => onMobileView(v)}
                    className={cn("rounded-md px-2.5 py-1 capitalize", mobileView === v ? "bg-card shadow-sm" : "text-muted-foreground")}>
              {v}
            </button>
          ))}
        </div>
        <Button size="sm" variant="ghost" onClick={onOpenIndex} aria-label="Index & Documents"><Database className="h-3.5 w-3.5" /><span className="hidden sm:inline">Index &amp; Documents</span></Button>
        <IconButton label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={onToggleTheme}>
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </IconButton>
      </div>
    </header>
  );
}
