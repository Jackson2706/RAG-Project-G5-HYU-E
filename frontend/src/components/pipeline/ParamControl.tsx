// Renders one hyperparameter from its registry spec. The control type, range, options and
// description all come from the backend; no per-parameter UI code exists.
import { Info, RefreshCw, X } from "lucide-react";
import { useEffect, useId, useState, type ReactNode } from "react";

import { Badge, IconButton, Slider, Switch, Tooltip } from "@/components/ui/primitives";
import type { SystemState } from "@/hooks/useSystem";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import type { ParameterSpec, ParamValue } from "@/types/api";

interface Props {
  spec: ParameterSpec;
  value: ParamValue;
  onChange: (v: ParamValue) => void;
  error?: string;
  disabled?: boolean;
  system: SystemState;
}

const inputCls = "h-8 w-full rounded-md border border-border bg-card px-2 text-sm text-foreground placeholder:text-muted-foreground disabled:opacity-50";

export function ParamControl({ spec, value, onChange, error, disabled, system }: Props) {
  const id = useId();
  const isDefault = JSON.stringify(value) === JSON.stringify(spec.default);
  return (
    <div className="space-y-1.5" data-testid={`param-${spec.name}`}>
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="flex min-w-0 items-center gap-1.5 text-xs font-medium text-foreground">
          <span className="truncate">{spec.label}</span>
          <Tooltip content={<span>{spec.description}<br /><span className="opacity-70">Default: {fmt(spec.default)} · scope: {spec.scope}</span></span>}>
            <Info className="h-3 w-3 shrink-0 text-muted-foreground" aria-label={spec.description} />
          </Tooltip>
          {spec.scope !== "runtime" && <Badge tone="warning">{spec.scope === "index" ? "re-index" : "re-ingest"}</Badge>}
        </label>
        {!isDefault && !disabled && (
          <button type="button" className="text-[11px] text-muted-foreground hover:text-foreground" onClick={() => onChange(spec.default)}>
            reset
          </button>
        )}
      </div>
      <Control id={id} spec={spec} value={value} onChange={onChange} disabled={disabled} system={system} />
      {error ? <p className="text-[11px] text-danger" role="alert">{error}</p> : <p className="text-[11px] leading-snug text-muted-foreground">{spec.description}</p>}
    </div>
  );
}

function fmt(v: ParamValue): string {
  if (v === null || v === "") return "none";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "none";
  return String(v);
}

function Control({ id, spec, value, onChange, disabled, system }: Omit<Props, "error"> & { id: string }) {
  switch (spec.control) {
    case "toggle":
      return <Switch id={id} checked={Boolean(value)} onCheckedChange={onChange} disabled={disabled} label={spec.label} />;
    case "slider":
      return <NumberSlider id={id} spec={spec} value={value as number} onChange={onChange} disabled={disabled} />;
    case "number":
      return <NumberInput id={id} spec={spec} value={value as number | null} onChange={onChange} disabled={disabled} />;
    case "select":
      return (
        <select id={id} className={inputCls} value={String(value)} disabled={disabled}
                onChange={(e) => onChange(spec.options?.find((o) => String(o.value) === e.target.value)?.value ?? e.target.value)}>
          {spec.options?.map((o) => <option key={String(o.value)} value={String(o.value)}>{o.label}</option>)}
        </select>
      );
    case "multiselect":
      return <MultiSelect spec={spec} value={(value as string[]) ?? []} onChange={onChange} disabled={disabled} />;
    case "tags":
      return <Tags id={id} value={(value as string[]) ?? []} onChange={onChange} disabled={disabled} />;
    case "textarea":
      return <textarea id={id} className={cn(inputCls, "h-16 py-1.5")} value={String(value ?? "")} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
    case "ollama_model":
      return <ModelPicker id={id} value={String(value ?? "")} onChange={onChange} disabled={disabled} system={system} />;
    default:
      return <input id={id} className={inputCls} value={String(value ?? "")} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
  }
}

function NumberSlider({ id, spec, value, onChange, disabled }: { id: string; spec: ParameterSpec; value: number; onChange: (v: ParamValue) => void; disabled?: boolean }) {
  const step = spec.step ?? (spec.type === "integer" ? 1 : 0.01);
  return (
    <div className="flex items-center gap-3">
      <Slider value={value} min={spec.min ?? 0} max={spec.max ?? 100} step={step} onChange={onChange} disabled={disabled} label={spec.label} />
      <NumberInput id={id} spec={spec} value={value} onChange={onChange} disabled={disabled} compact />
    </div>
  );
}

/** Free numeric entry; the backend reports out-of-range values. Empty → null for nullable params. */
function NumberInput({ id, spec, value, onChange, disabled, compact }: { id: string; spec: ParameterSpec; value: number | null; onChange: (v: ParamValue) => void; disabled?: boolean; compact?: boolean }) {
  const [text, setText] = useState(value == null ? "" : String(value));
  useEffect(() => setText(value == null ? "" : String(value)), [value]);
  return (
    <div className={cn("flex items-center gap-1", compact ? "w-24 shrink-0" : "w-full")}>
      <input
        id={id}
        inputMode="decimal"
        className={cn(inputCls, "font-mono text-xs")}
        value={text}
        placeholder={spec.nullable ? "none" : undefined}
        disabled={disabled}
        aria-label={spec.label}
        onChange={(e) => {
          setText(e.target.value);
          const raw = e.target.value.trim();
          if (raw === "" && spec.nullable) onChange(null);
          else if (raw !== "" && !Number.isNaN(Number(raw))) onChange(Number(raw));
        }}
      />
      {spec.unit && <span className="text-[11px] text-muted-foreground">{spec.unit}</span>}
    </div>
  );
}

function MultiSelect({ spec, value, onChange, disabled }: { spec: ParameterSpec; value: string[]; onChange: (v: ParamValue) => void; disabled?: boolean }) {
  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label={spec.label}>
      {spec.options?.map((o) => {
        const on = value.includes(String(o.value));
        return (
          <button key={String(o.value)} type="button" disabled={disabled} aria-pressed={on}
                  onClick={() => onChange(on ? value.filter((v) => v !== o.value) : [...value, String(o.value)])}
                  className={cn("rounded-md border px-2 py-0.5 text-xs transition-colors",
                    on ? "border-primary bg-accent text-primary" : "border-border text-muted-foreground hover:bg-muted")}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function Tags({ id, value, onChange, disabled }: { id: string; value: string[]; onChange: (v: ParamValue) => void; disabled?: boolean }) {
  const [text, setText] = useState("");
  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-border bg-card p-1">
      {value.map((t) => (
        <span key={t} className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
          {JSON.stringify(t).slice(1, -1)}
          <button type="button" aria-label={`Remove ${t}`} disabled={disabled} onClick={() => onChange(value.filter((v) => v !== t))}><X className="h-3 w-3" /></button>
        </span>
      ))}
      <input id={id} className="h-6 min-w-24 flex-1 bg-transparent px-1 text-xs outline-none" placeholder="Add and press Enter" value={text} disabled={disabled}
             onChange={(e) => setText(e.target.value)}
             onKeyDown={(e) => {
               if (e.key === "Enter" && text) {
                 e.preventDefault();
                 if (!value.includes(text)) onChange([...value, text]);
                 setText("");
               }
             }} />
    </div>
  );
}

function ModelPicker({ id, value, onChange, disabled, system }: { id: string; value: string; onChange: (v: ParamValue) => void; disabled?: boolean; system: SystemState }) {
  const { models, defaultModel, ollama, loadingModels, refreshModels } = system;
  const [info, setInfo] = useState<{ capabilities: string[]; context_length: number | null } | null>(null);
  const effective = value || defaultModel || "";
  useEffect(() => {
    setInfo(null);
    if (effective && models.some((m) => m.name === effective)) api.ollamaShow(effective).then(setInfo).catch(() => setInfo(null));
  }, [effective, models]);
  const missing = value && !models.some((m) => m.name === value);
  let status: ReactNode = null;
  if (ollama && !ollama.reachable) status = <p className="text-[11px] text-danger">{ollama.error} {ollama.hint}</p>;
  else if (ollama?.reachable && !models.length) status = <p className="text-[11px] text-warning">{ollama.hint}</p>;
  else if (missing) status = <p className="text-[11px] text-danger">“{value}” is not installed.</p>;
  const selected = models.find((m) => m.name === effective);
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1">
        <select id={id} className={inputCls} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          <option value="">{defaultModel ? `Default (${defaultModel})` : "Default (none installed)"}</option>
          {models.map((m) => <option key={m.name} value={m.name}>{m.name}</option>)}
          {missing && <option value={value}>{value} (missing)</option>}
        </select>
        <IconButton label="Refresh installed models" onClick={() => void refreshModels()} disabled={loadingModels}>
          <RefreshCw className={cn("h-3.5 w-3.5", loadingModels && "animate-spin")} />
        </IconButton>
      </div>
      {selected && (
        <div className="flex flex-wrap gap-1">
          {selected.parameter_size && <Badge>{selected.parameter_size}</Badge>}
          {selected.quantization && <Badge>{selected.quantization}</Badge>}
          {info?.context_length && <Badge>ctx {info.context_length.toLocaleString()}</Badge>}
          {info?.capabilities.map((c) => <Badge key={c} tone={c === "thinking" ? "warning" : "neutral"}>{c}</Badge>)}
        </div>
      )}
      {info?.capabilities.includes("thinking") && (
        <p className="text-[11px] text-muted-foreground">Thinking model: reasoning output is requested off and stripped; it is never displayed.</p>
      )}
      {status}
    </div>
  );
}
