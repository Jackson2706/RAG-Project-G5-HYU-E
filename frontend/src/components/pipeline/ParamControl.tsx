// Draws one hyperparameter from its registry definition (ParamDef). There is no code here for
// specific parameters: the backend's `ui` field decides which control is shown.
import { RefreshCw } from "lucide-react";

import { Badge, IconButton, Slider } from "@/components/ui/primitives";
import type { SystemState } from "@/hooks/useSystem";
import type { ParamDef, ParamValue } from "@/types/api";

const inputCls = "h-8 rounded-md border border-border bg-card px-2 text-sm disabled:opacity-50";

export function ParamControl({ id, name, def, value, error, onChange, system, disabled }: {
  id: string; name: string; def: ParamDef; value: ParamValue; error?: string; onChange: (v: ParamValue) => void; system: SystemState; disabled?: boolean;
}) {
  const step = def.step ?? (def.type === "integer" ? 1 : 0.01);
  let control;
  if (def.ui === "ollama_model") {
    control = (
      <div className="flex items-center gap-1">
        <select id={id} className={`${inputCls} w-full`} value={String(value)} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          <option value="">Default ({system.defaultModel ?? "none installed"})</option>
          {system.models.map((m) => <option key={m.name} value={m.name}>{m.name}{m.parameter_size ? ` · ${m.parameter_size}` : ""}</option>)}
        </select>
        <IconButton label="Refresh installed models" onClick={() => void system.refresh()}><RefreshCw className="h-3.5 w-3.5" /></IconButton>
      </div>
    );
  } else if (def.ui === "toggle") {
    control = <input id={id} type="checkbox" role="switch" className="h-4 w-4 accent-[var(--primary)]" checked={Boolean(value)} disabled={disabled}
                     onChange={(e) => onChange(e.target.checked)} />;
  } else if (def.ui === "select") {
    control = (
      <select id={id} className={`${inputCls} w-full`} value={String(value)} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        {def.options?.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  } else if (def.ui === "text") {
    control = <input id={id} className={`${inputCls} w-full`} value={String(value)} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
  } else {
    const number = (
      <input id={id} type="number" className={`${inputCls} w-20 font-mono text-xs`} value={String(value)} step={step} disabled={disabled}
             onChange={(e) => e.target.value !== "" && onChange(Number(e.target.value))} />
    );
    control = def.ui === "slider" && def.min != null && def.max != null ? (
      <div className="flex items-center gap-3">
        <Slider value={Number(value)} min={def.min} max={def.max} step={step} onChange={onChange} label={def.label} />
        {number}
      </div>
    ) : number;
  }
  return (
    <div className="space-y-1.5" data-testid={`param-${name}`}>
      <label htmlFor={id} className="flex items-center gap-1.5 text-xs font-medium">
        {def.label}
        {def.scope !== "runtime" && <Badge tone="warning">re-index needed</Badge>}
      </label>
      {control}
      {error ? <p role="alert" className="text-[11px] text-danger">{error}</p> : <p className="text-[11px] leading-snug text-muted-foreground">{def.description}</p>}
    </div>
  );
}
