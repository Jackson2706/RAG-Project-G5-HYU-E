import { Download, Loader2, RefreshCw, RotateCcw, Save, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { DisabledStage } from "@/components/pipeline/DisabledStage";
import { StageConfigCard } from "@/components/pipeline/StageConfigCard";
import { Button } from "@/components/ui/primitives";
import { CUSTOM, groupStartsAt, type PipelineConfigState } from "@/hooks/usePipelineConfig";
import type { SystemState } from "@/hooks/useSystem";
import { api } from "@/services/api";

const groupLabel = (label: string | null) =>
  label && <p className="px-1 pt-1 text-[11px] font-semibold uppercase tracking-wide text-primary">{label}</p>;

/** Re-index buttons + a warning when the chunk settings differ from the current index. */
function Reindex({ config, system }: { config: PipelineConfigState; system: SystemState }) {
  const [running, setRunning] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const index = system.health?.index;
  const chunking = config.choices!.chunking;
  const built = index?.chunking;
  const differs = !!built && (built.method !== chunking.method || built.chunk_size !== chunking.params.chunk_size || built.chunk_overlap !== chunking.params.chunk_overlap);
  const run = async (folder: string) => {
    setRunning(folder);
    setMessage(null);
    try {
      const r = await api.ingest(folder, config.choices!);
      setMessage(`Indexed ${r.documents} documents → ${r.chunks} chunks.${r.errors.length ? ` Problems: ${r.errors.join("; ")}` : ""}`);
      await system.refresh();
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setRunning(null);
    }
  };
  return (
    <div className="space-y-2 rounded-xl border border-border bg-surface p-3 text-xs">
      <p>
        Current index: {index ? `${index.documents} documents, ${index.chunks} chunks` : "unknown"}
        {built && ` (chunk size ${built.chunk_size}, overlap ${built.chunk_overlap})`}
      </p>
      {differs && <p className="text-warning">The ingestion settings below differ from the current index. Re-index to apply them.</p>}
      <div className="flex flex-wrap gap-1.5">
        {["HYU/raw", "HYU/synthetic_fixture"].map((folder) => (
          <Button key={folder} size="sm" disabled={!!running || !config.valid} onClick={() => void run(folder)}>
            {running === folder ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />} Re-index Report/data/{folder}
          </Button>
        ))}
      </div>
      {message && <p role="status">{message}</p>}
    </div>
  );
}

const selectCls = "h-8 w-full rounded-md border border-border bg-card px-2 text-sm";

/** Offline settings that differ from how the selected index was built (then the index does not match them). */
function offlineDifferences(config: PipelineConfigState): string[] {
  const built = config.indexes.find((i) => i.index_id === config.indexId)?.manifest?.config;
  if (!built) return [];
  return Object.entries(built)
    .filter(([stageId, b]) => JSON.stringify(config.choices![stageId]) !== JSON.stringify(b))
    .map(([stageId]) => config.stages.find((s) => s.stage_id === stageId)?.name ?? stageId);
}

/** Experiment presets (B0, O0–O8, R0–R14), the index to search, and saving/sharing a configuration. */
function ExperimentPanel({ config }: { config: PipelineConfigState }) {
  const file = useRef<HTMLInputElement>(null);
  const [note, setNote] = useState<string | null>(null);
  const preset = config.presets.find((p) => p.id === config.presetId);
  const index = config.indexes.find((i) => i.index_id === config.indexId);
  const differs = offlineDifferences(config);
  const kinds = [["baseline", "Baseline"], ["offline", "Offline (needs its own index)"], ["online", "Online"], ["proposed", "Reserved"]] as const;
  const download = () => {
    const url = URL.createObjectURL(new Blob([config.exportJson()], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "hyu-compass-config.json" });
    a.click();
    URL.revokeObjectURL(url);
  };
  const load = async (f: File | undefined) => {
    if (!f) return;
    try {
      config.importJson(await f.text());
      setNote(`Imported ${f.name}.`);
    } catch (err) {
      setNote(`Import failed: ${(err as Error).message}`);
    }
  };
  return (
    <section className="space-y-2 rounded-xl border border-border bg-surface p-3" data-testid="experiment-panel">
      <label htmlFor="preset" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Experiment preset</label>
      <select id="preset" className={selectCls} value={config.presetId ?? ""} onChange={(e) => config.applyPreset(e.target.value || null)}>
        <option value="">Manual configuration</option>
        {config.hasCustom && <option value={CUSTOM}>Custom (saved)</option>}
        {kinds.map(([kind, label]) => (
          <optgroup key={kind} label={label}>
            {config.presets.filter((p) => p.kind === kind).map((p) => (
              <option key={p.id} value={p.id} disabled={!p.config}>{p.name}{p.enabled ? "" : " — not available"}</option>
            ))}
          </optgroup>
        ))}
      </select>
      {preset && <p className="text-[11px] leading-snug text-muted-foreground">{preset.description}{config.modified && " · modified"}</p>}
      <label htmlFor="index" className="block pt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Index to search</label>
      <select id="index" className={selectCls} value={config.indexId} onChange={(e) => config.selectIndex(e.target.value)}>
        {config.indexes.length === 0 && <option value="default">default (the app's index)</option>}
        {config.indexes.map((i) => (
          <option key={i.index_id} value={i.index_id}>
            {i.index_id === "default" ? "default (the app's index)" : i.index_id} · {i.info.documents} docs, {i.info.chunks} chunks
          </option>
        ))}
      </select>
      {index?.manifest?.embedding_contract && (
        <p className="text-[11px] text-muted-foreground">
          Built with {index.manifest.config?.chunking?.method} {JSON.stringify(index.manifest.config?.chunking?.params ?? {})},
          {" "}{index.manifest.embedding_contract.model}{index.manifest.vector_index?.hnsw_built ? ", HNSW graph built" : ""}.
        </p>
      )}
      {differs.length > 0 && (
        <p role="status" className="text-[11px] text-warning">
          {differs.join(", ")} differ from how this index was built: they only take effect after re-indexing.
        </p>
      )}
      <div className="flex flex-wrap gap-1.5 pt-1">
        <Button size="sm" variant="ghost" disabled={!preset} onClick={() => config.applyPreset(config.presetId)}><RotateCcw className="h-3.5 w-3.5" /> Reset to preset</Button>
        <Button size="sm" variant="ghost" onClick={config.resetAll}><RotateCcw className="h-3.5 w-3.5" /> Reset to defaults</Button>
        <Button size="sm" variant="ghost" onClick={() => { config.saveCustom(); setNote("Saved as Custom."); }}><Save className="h-3.5 w-3.5" /> Save custom</Button>
        <Button size="sm" variant="ghost" onClick={download}><Download className="h-3.5 w-3.5" /> Export JSON</Button>
        <Button size="sm" variant="ghost" onClick={() => file.current?.click()}><Upload className="h-3.5 w-3.5" /> Import JSON</Button>
        <input ref={file} type="file" accept="application/json" className="hidden" aria-label="Import configuration file"
               onChange={(e) => void load(e.target.files?.[0])} />
      </div>
      {note && <p role="status" className="text-[11px] text-muted-foreground">{note}</p>}
    </section>
  );
}

/** Every registered block, in pipeline order. Blocks and controls come from GET /api/pipeline/registry. */
export function ConfigurationTab({ config, system }: { config: PipelineConfigState; system: SystemState }) {
  if (!config.choices) return <p className="p-6 text-sm text-muted-foreground">{config.loadError ?? "Loading the method registry…"}</p>;
  const general = config.errors.filter((e) => !e.stage_id);
  return (
    <div className="space-y-4 p-3">
      <p className="text-xs text-muted-foreground">Methods and settings come from <span className="font-mono">registry.py</span>; presets from <span className="font-mono">presets.py</span>.</p>
      <ExperimentPanel config={config} />
      {general.map((e) => <p key={e.message} role="alert" className="text-xs text-danger">{e.message}</p>)}
      {(["online", "offline"] as const).map((phase) => (
        <section key={phase} className="space-y-1.5">
          <h3 className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {phase === "online" ? "Answering a question (runs every time)" : "Ingestion (applies after re-indexing)"}
          </h3>
          {phase === "offline" && (config.indexId === "default" ? <Reindex config={config} system={system} /> : (
            <p className="rounded-xl border border-border bg-surface p-3 text-xs text-muted-foreground">
              Benchmark index <span className="font-mono">{config.indexId}</span> is built by the evaluation runner (python -m evaluation.runner), not here.
            </p>
          ))}
          <ol className="space-y-1.5">
            {config.stages.filter((s) => s.phase === phase).map((stage, i, list) => (
              <li key={stage.stage_id} className={stage.group ? "border-l-2 border-primary/30 pl-2" : undefined}>
                {groupLabel(groupStartsAt(list, i))}
                {stage.implemented ? <StageConfigCard stage={stage} config={config} system={system} /> : <DisabledStage stage={stage} />}
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}
