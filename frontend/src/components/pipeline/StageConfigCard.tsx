import { CheckCircle2, ChevronRight, RotateCcw } from "lucide-react";

import { ParamControl } from "@/components/pipeline/ParamControl";
import { Badge } from "@/components/ui/primitives";
import { methodOf, type PipelineConfigState } from "@/hooks/usePipelineConfig";
import type { SystemState } from "@/hooks/useSystem";
import { cn } from "@/lib/utils";
import type { StageDef } from "@/types/api";

const OFF = "__off__";

/** One block that has at least one implemented method: choose the method and its parameters. */
export function StageConfigCard({ stage, config, system }: { stage: StageDef; config: PipelineConfigState; system: SystemState }) {
  const choice = config.choices![stage.stage_id];
  const method = methodOf(stage, choice.method);
  const errors = config.errors.filter((e) => e.stage_id === stage.stage_id);
  const stageError = errors.find((e) => !e.param);
  const params = Object.entries(method?.parameters ?? {});

  return (
    <details className={cn("group rounded-xl border bg-card", errors.length ? "border-danger/60" : "border-border")} data-testid={`stage-config-${stage.stage_id}`}>
      <summary className="flex list-none items-center gap-2 px-3 py-2.5 [&::-webkit-details-marker]:hidden">
        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden />
        <CheckCircle2 className={cn("h-4 w-4 shrink-0", method ? "text-success" : "text-muted-foreground")} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{stage.name}</p>
          <p className="truncate text-[11px] text-muted-foreground">{method ? method.name : "Off — this stage is skipped"}</p>
        </div>
        {errors.length > 0 && <Badge tone="danger">error</Badge>}
      </summary>

      <div className="space-y-3 border-t border-border px-3 py-3">
        <p className="text-xs leading-relaxed text-muted-foreground">{stage.description}</p>
        <div className="space-y-1.5">
          <label htmlFor={`method-${stage.stage_id}`} className="text-xs font-medium">Method</label>
          <select id={`method-${stage.stage_id}`} className="h-8 w-full rounded-md border border-border bg-card px-2 text-sm"
                  value={choice.method ?? OFF} onChange={(e) => config.setMethod(stage, e.target.value === OFF ? null : e.target.value)}>
            {stage.optional && <option value={OFF}>Off — skip this stage</option>}
            {stage.methods.map((m) => (
              // Planned methods are listed so you can see what is coming, but cannot be chosen.
              <option key={m.method_id} value={m.method_id} disabled={!m.implemented}>{m.name}{m.implemented ? "" : " — not implemented"}</option>
            ))}
          </select>
          {method && (
            <p className="text-[11px] leading-snug text-muted-foreground">
              {method.description}{" "}
              <span className="font-mono">blocks/{method.file} · {method.class_name} ← {stage.base_class}</span>
            </p>
          )}
        </div>
        {stageError && <p role="alert" className="rounded-md bg-danger/10 px-2 py-1.5 text-xs text-danger">{stageError.message}</p>}
        {params.map(([name, def]) => (
          <ParamControl key={name} id={`${stage.stage_id}-${name}`} name={name} def={def} value={choice.params[name] ?? def.default}
                        error={errors.find((e) => e.param === name)?.message} system={system}
                        onChange={(v) => config.setParam(stage.stage_id, name, v)} />
        ))}
        {method && params.length === 0 && <p className="text-[11px] text-muted-foreground">This method has no settings.</p>}
        <button type="button" className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground" onClick={() => config.resetStage(stage)}>
          <RotateCcw className="h-3 w-3" /> Reset stage to defaults
        </button>
      </div>
    </details>
  );
}
