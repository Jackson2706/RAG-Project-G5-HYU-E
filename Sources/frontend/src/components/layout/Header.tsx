import { Compass, Moon, Sun } from "lucide-react";

import { IconButton, Tooltip } from "@/components/ui/primitives";
import type { SystemState } from "@/hooks/useSystem";
import { cn } from "@/lib/utils";

function Status({ ok, label, detail }: { ok?: boolean; label: string; detail?: string }) {
  return (
    <Tooltip content={detail ?? (ok ? `${label} is connected` : `${label} is not available`)}>
      <span tabIndex={0} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <span aria-hidden className={cn("h-2 w-2 rounded-full", ok === undefined ? "bg-border" : ok ? "bg-success" : "bg-danger")} />
        {label}<span className="sr-only">{ok ? " connected" : " not available"}</span>
      </span>
    </Tooltip>
  );
}

export function Header({ system, dark, onToggleTheme, mobileView, onMobileView }: {
  system: SystemState; dark: boolean; onToggleTheme: () => void; mobileView: "chat" | "pipeline"; onMobileView: (v: "chat" | "pipeline") => void;
}) {
  const h = system.health;
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border px-3">
      <Compass className="h-5 w-5 text-primary" aria-hidden />
      <span className="whitespace-nowrap font-semibold tracking-tight">HYU Compass</span>
      <div className="ml-auto hidden items-center gap-3 md:flex">
        {system.error ? <span className="text-xs text-danger">{system.error}</span> : (
          <>
            <Status ok={h?.mongodb.ok} label="MongoDB" detail={h?.mongodb.error} />
            <Status ok={h?.qdrant.ok} label="Qdrant" detail={h?.qdrant.error} />
            <Status ok={h?.ollama.ok} label="Ollama" detail={h?.ollama.error} />
            <Status ok={h ? !!h.index?.chunks : undefined} label="Index" detail={h?.index ? `${h.index.documents} documents, ${h.index.chunks} chunks` : "Nothing indexed"} />
          </>
        )}
      </div>
      <div className="ml-auto flex items-center gap-1 md:ml-0">
        <div role="tablist" aria-label="View" className="inline-flex rounded-lg bg-muted p-0.5 text-xs md:hidden">
          {(["chat", "pipeline"] as const).map((v) => (
            <button key={v} role="tab" type="button" aria-selected={mobileView === v} onClick={() => onMobileView(v)}
                    className={cn("rounded-md px-2.5 py-1 capitalize", mobileView === v ? "bg-card shadow-sm" : "text-muted-foreground")}>{v}</button>
          ))}
        </div>
        <IconButton label={dark ? "Light theme" : "Dark theme"} onClick={onToggleTheme}>{dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</IconButton>
      </div>
    </header>
  );
}
