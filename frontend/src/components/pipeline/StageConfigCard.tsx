import { AlertTriangle, ChevronRight, RotateCcw } from "lucide-react";

import { ParamControl } from "@/components/pipeline/ParamControl";
import { Badge, Switch } from "@/components/ui/primitives";
import type { SystemState } from "@/hooks/useSystem";
import { isVisible, issuesFor, methodOf, resetStage, setEnabled, setMethod, setParam } from "@/lib/config";
import { cn } from "@/lib/utils";
import type { ImplementationStatus, PipelineConfig, StageSpec, ValidationResult } from "@/types/api";

export const STATUS_TONE: Record<ImplementationStatus, "success" | "warning" | "neutral"> = {
  implemented: "success",
  planned: "warning",
  unavailable: "neutral",
};

interface Props {
  spec: StageSpec;
  draft: PipelineConfig;
  onChange: (next: PipelineConfig) => void;
  validation: ValidationResult | null;
  advanced: boolean;
  system: SystemState;
  index: number;
}

export function StageConfigCard({ spec, draft, onChange, validation, advanced, system, index }: Props) {
  const stage = draft.stages[spec.stage_id];
  const method = methodOf(spec, stage.method)!;
  const enabled = stage.enabled ?? spec.enabled;
  const { errors, warnings } = issuesFor(validation, spec.stage_id);
  const stageErrors = errors.filter((e) => !e.param);
  const params = method.parameters.filter((p) => (advanced || p.level === "basic") && isVisible(p, stage.params));
  const hidden = method.parameters.filter((p) => p.level === "advanced" && isVisible(p, stage.params)).length;
  const offline = spec.category === "offline";

  return (
    <details className={cn("group rounded-xl border bg-card", errors.length ? "border-danger/60" : "border-border")} data-testid={`stage-config-${spec.stage_id}`}>
      <summary className="flex list-none items-center gap-2 px-3 py-2.5 [&::-webkit-details-marker]:hidden">
        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden />
        <span className="w-5 shrink-0 text-right font-mono text-[11px] text-muted-foreground">{index}</span>
        <span className={cn("min-w-0 flex-1 truncate text-sm font-medium", !enabled && "text-muted-foreground line-through decoration-1")}>{spec.stage_name}</span>
        {errors.length > 0 && <AlertTriangle className="h-3.5 w-3.5 text-danger" aria-label="Configuration error" />}
        <Badge tone={STATUS_TONE[method.status]}>{method.status}</Badge>
        {spec.can_disable && (
          <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
            <Switch checked={enabled} onCheckedChange={(v) => onChange(setEnabled(draft, spec.stage_id, v))} label={`Enable ${spec.stage_name}`} />
          </span>
        )}
      </summary>

      <div className="space-y-3 border-t border-border px-3 py-3">
        <p className="text-xs leading-relaxed text-muted-foreground">{spec.description}</p>
        {offline && (
          <p className="rounded-md bg-warning/10 px-2 py-1.5 text-[11px] text-warning">
            Offline stage — changes apply only after rebuilding the index (Index &amp; Documents → Rebuild).
          </p>
        )}

        <div className="space-y-1.5">
          <label className="text-xs font-medium" htmlFor={`${spec.stage_id}-method`}>Method</label>
          <select
            id={`${spec.stage_id}-method`}
            className="h-8 w-full rounded-md border border-border bg-card px-2 text-sm"
            value={method.method_id}
            onChange={(e) => onChange(setMethod(draft, spec, e.target.value))}
          >
            {spec.available_methods.map((m) => (
              // Planned methods are visible but cannot be chosen while the stage is enabled.
              <option key={m.method_id} value={m.method_id} disabled={m.status !== "implemented" && enabled}>
                {m.display_name}{m.status !== "implemented" ? ` — ${m.status}` : ""}
              </option>
            ))}
          </select>
          <p className="text-[11px] leading-snug text-muted-foreground">{method.description}</p>
          {method.constraints.map((c) => <p key={c} className="text-[11px] text-info">ⓘ {c}</p>)}
          {method.implementation && <p className="font-mono text-[10px] text-muted-foreground">{method.implementation}</p>}
        </div>

        {stageErrors.map((e) => <p key={e.message} role="alert" className="rounded-md bg-danger/10 px-2 py-1.5 text-xs text-danger">{e.message}</p>)}
        {warnings.map((w) => <p key={w.message} className="rounded-md bg-warning/10 px-2 py-1.5 text-[11px] text-warning">{w.message}</p>)}

        {params.length > 0 && (
          <fieldset className={cn("space-y-3", !enabled && "opacity-60")} disabled={!enabled && spec.can_disable}>
            {params.map((p) => (
              <ParamControl key={p.name} spec={p} value={stage.params[p.name] ?? p.default} system={system}
                            disabled={method.status !== "implemented" || (!enabled && spec.can_disable)}
                            error={errors.find((e) => e.param === p.name)?.message}
                            onChange={(v) => onChange(setParam(draft, spec.stage_id, p.name, v))} />
            ))}
          </fieldset>
        )}
        {!advanced && hidden > 0 && <p className="text-[11px] text-muted-foreground">{hidden} advanced setting(s) hidden — switch to Advanced view.</p>}
        {method.parameters.length === 0 && <p className="text-[11px] text-muted-foreground">This method has no hyperparameters.</p>}

        <button type="button" className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground" onClick={() => onChange(resetStage(draft, spec))}>
          <RotateCcw className="h-3 w-3" /> Reset stage to defaults
        </button>
      </div>
    </details>
  );
}
