import { CheckCircle2, Download, Loader2, RotateCcw, Save, Upload, XCircle } from "lucide-react";
import { useRef, useState } from "react";

import { StageConfigCard } from "@/components/pipeline/StageConfigCard";
import { Badge, Button, Tooltip } from "@/components/ui/primitives";
import type { PipelineConfigState } from "@/hooks/usePipelineConfig";
import type { SystemState } from "@/hooks/useSystem";
import { stageById } from "@/lib/config";
import { cn } from "@/lib/utils";

export function ConfigurationTab({ cfg, system }: { cfg: PipelineConfigState; system: SystemState }) {
  const { registry, draft, setDraft, validation, validating, presets } = cfg;
  const [advanced, setAdvanced] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  if (!registry || !draft) return null;
  const stages = stageById(registry);
  const globalErrors = validation?.errors.filter((e) => !e.stage_id) ?? [];

  const exportJson = () => {
    const blob = new Blob([JSON.stringify({ config: draft }, null, 2)], { type: "application/json" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `hyu-compass-config-${validation?.resolved?.config_hash ?? "draft"}.json` });
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const save = async () => {
    const name = window.prompt("Preset name");
    if (!name) return;
    try {
      await cfg.savePreset(name, "");
      setMessage(`Saved preset “${name}”.`);
    } catch (err) {
      setMessage((err as Error).message);
    }
  };

  return (
    <div className="space-y-4 p-3">
      <div className="space-y-2 rounded-xl border border-border bg-surface p-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Presets</h3>
          <div className="flex items-center gap-2 text-[11px]" aria-live="polite">
            {validating ? (
              <span className="inline-flex items-center gap-1 text-muted-foreground"><Loader2 className="h-3 w-3 animate-spin" /> validating</span>
            ) : validation?.valid ? (
              <span className="inline-flex items-center gap-1 text-success"><CheckCircle2 className="h-3 w-3" /> valid · <span className="font-mono">{validation.resolved?.config_hash}</span></span>
            ) : validation ? (
              <span className="inline-flex items-center gap-1 text-danger"><XCircle className="h-3 w-3" /> {validation.errors.length} error(s)</span>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {presets.map((p) => (
            <Tooltip key={p.preset_id} content={p.available ? p.description : `Unavailable: ${p.unavailable_reason}`}>
              <span>
                <Button size="sm" variant="outline" disabled={!p.available} onClick={() => cfg.loadPreset(p)} className={cn(!p.available && "line-through")}>
                  {p.name}
                  {!p.builtin && <Badge>saved</Badge>}
                </Button>
              </span>
            </Tooltip>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5 border-t border-border pt-2">
          <Button size="sm" variant="ghost" onClick={cfg.resetAll}><RotateCcw className="h-3.5 w-3.5" /> Reset all</Button>
          <Button size="sm" variant="ghost" onClick={save} disabled={!validation?.valid}><Save className="h-3.5 w-3.5" /> Save preset</Button>
          <Button size="sm" variant="ghost" onClick={exportJson}><Download className="h-3.5 w-3.5" /> Export JSON</Button>
          <Button size="sm" variant="ghost" onClick={() => fileRef.current?.click()}><Upload className="h-3.5 w-3.5" /> Import JSON</Button>
          <input ref={fileRef} type="file" accept="application/json" className="hidden" aria-label="Import configuration JSON"
                 onChange={async (e) => {
                   const f = e.target.files?.[0];
                   if (!f) return;
                   try {
                     cfg.importConfig(JSON.parse(await f.text()));
                     setMessage(`Imported ${f.name}.`);
                   } catch (err) {
                     setMessage(`Import failed: ${(err as Error).message}`);
                   }
                   e.target.value = "";
                 }} />
        </div>
        {message && <p className="text-[11px] text-muted-foreground" role="status">{message}</p>}
        {globalErrors.map((e) => <p key={e.message} className="text-xs text-danger" role="alert">{e.message}</p>)}
      </div>

      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">Controls are generated from the backend registry.</p>
        <div className="inline-flex rounded-lg bg-muted p-0.5 text-xs" role="radiogroup" aria-label="Parameter detail level">
          {(["Basic", "Advanced"] as const).map((v) => (
            <button key={v} type="button" role="radio" aria-checked={advanced === (v === "Advanced")}
                    onClick={() => setAdvanced(v === "Advanced")}
                    className={cn("rounded-md px-2.5 py-1", advanced === (v === "Advanced") ? "bg-card shadow-sm" : "text-muted-foreground")}>
              {v}
            </button>
          ))}
        </div>
      </div>

      {(["online", "offline"] as const).map((group) => (
        <section key={group} className="space-y-1.5">
          <h3 className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {group === "online" ? "Online pipeline (per question)" : "Offline ingestion & index"}
          </h3>
          {(group === "online" ? registry.online_order : registry.offline_order).map((id, i) => (
            <StageConfigCard key={id} spec={stages[id]} draft={draft} onChange={setDraft} validation={validation} advanced={advanced} system={system} index={i + 1} />
          ))}
        </section>
      ))}
    </div>
  );
}
