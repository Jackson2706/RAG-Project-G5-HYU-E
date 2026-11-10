import { Lock } from "lucide-react";

import type { StageDef } from "@/types/api";

/**
 * A block with no implemented method (implemented: false in backend/app/rag/registry.py).
 * Visible so the whole pipeline is shown, but muted, disabled and never expanded or executed.
 */
export function DisabledStage({ stage }: { stage: StageDef }) {
  return (
    <div aria-disabled="true" data-testid={`disabled-stage-${stage.stage_id}`}
         className="pointer-events-none select-none rounded-xl border border-dashed border-border bg-muted/50 px-3 py-2 opacity-55 grayscale">
      <div className="flex items-start gap-2.5">
        <Lock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-muted-foreground">{stage.name}</span>
            <span className="shrink-0 rounded bg-border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Not implemented</span>
          </div>
          <p className="truncate text-[11px] text-muted-foreground">{stage.description}</p>
        </div>
      </div>
      <select disabled aria-label={`${stage.name} method (not implemented)`}
              className="mt-1.5 h-7 w-full rounded-md border border-border bg-muted px-2 text-[11px] text-muted-foreground">
        {stage.methods.map((m) => <option key={m.method_id}>{m.name} — {m.file} (planned)</option>)}
      </select>
    </div>
  );
}
