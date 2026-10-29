import { Loader2, RefreshCw, RotateCcw } from "lucide-react";
import { useState } from "react";

import { DisabledStage } from "@/components/pipeline/DisabledStage";
import { StageConfigCard } from "@/components/pipeline/StageConfigCard";
import { Button } from "@/components/ui/primitives";
import { groupStartsAt, type PipelineConfigState } from "@/hooks/usePipelineConfig";
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
        {["raw", "samples"].map((folder) => (
          <Button key={folder} size="sm" disabled={!!running || !config.valid} onClick={() => void run(folder)}>
            {running === folder ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />} Re-index data/{folder}
          </Button>
        ))}
      </div>
      {message && <p role="status">{message}</p>}
    </div>
  );
}

/** Every registered block, in pipeline order. Blocks and controls come from GET /api/pipeline/registry. */
export function ConfigurationTab({ config, system }: { config: PipelineConfigState; system: SystemState }) {
  if (!config.choices) return <p className="p-6 text-sm text-muted-foreground">{config.loadError ?? "Loading the method registry…"}</p>;
  const general = config.errors.filter((e) => !e.stage_id);
  return (
    <div className="space-y-4 p-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">Methods and settings come from <span className="font-mono">registry.py</span>.</p>
        <Button size="sm" variant="ghost" onClick={config.resetAll}><RotateCcw className="h-3.5 w-3.5" /> Reset all</Button>
      </div>
      {general.map((e) => <p key={e.message} role="alert" className="text-xs text-danger">{e.message}</p>)}
      {(["online", "offline"] as const).map((phase) => (
        <section key={phase} className="space-y-1.5">
          <h3 className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {phase === "online" ? "Answering a question (runs every time)" : "Ingestion (applies after re-indexing)"}
          </h3>
          {phase === "offline" && <Reindex config={config} system={system} />}
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
