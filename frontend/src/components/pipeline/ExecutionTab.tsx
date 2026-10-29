import { Activity } from "lucide-react";

import { DisabledStage } from "@/components/pipeline/DisabledStage";
import { StageTraceCard } from "@/components/pipeline/StageTraceCard";
import { Badge, CopyButton } from "@/components/ui/primitives";
import type { ChatState } from "@/hooks/useChat";
import { groupStartsAt } from "@/hooks/usePipelineConfig";
import { formatMs } from "@/lib/utils";
import type { StageDef } from "@/types/api";

/** What really happened for one request, stage by stage, in pipeline order (from the registry). */
export function ExecutionTab({ stages, chat }: { stages: StageDef[]; chat: ChatState }) {
  const answers = chat.messages.filter((m) => m.role === "assistant" && m.requestId);
  const live = chat.selected ? chat.traces[chat.selected] : undefined;

  if (!live) {
    return (
      <div className="flex flex-col items-center gap-2 p-10 text-center text-sm text-muted-foreground">
        <Activity className="h-6 w-6" />
        <p>Ask a question to see each stage’s real input, output and timing.</p>
      </div>
    );
  }
  const final = live.final;
  return (
    <div className="space-y-3 p-3">
      <div className="space-y-2 rounded-xl border border-border bg-surface p-3">
        <label htmlFor="request" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Request</label>
        <select id="request" className="h-8 w-full rounded-md border border-border bg-card px-2 text-sm" value={live.requestId}
                onChange={(e) => void chat.select(e.target.value)}>
          {answers.map((m, i) => (
            <option key={m.requestId} value={m.requestId}>#{i + 1} {chat.traces[m.requestId!]?.question.slice(0, 70)}</option>
          ))}
        </select>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={live.status === "completed" ? "success" : live.status === "failed" ? "danger" : "info"}>{live.status}</Badge>
          {final?.total_ms != null && <Badge>total {formatMs(final.total_ms)}</Badge>}
          {final && <Badge>{stages.filter((s) => final.config[s.stage_id]?.method).length} blocks active</Badge>}
          <span className="ml-auto inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
            {live.requestId.slice(0, 10)} <CopyButton text={live.requestId} label="Copy request ID" />
          </span>
        </div>
        {final?.error && <p className="text-xs text-danger" role="alert">{final.error}</p>}
      </div>
      <ol className="space-y-1.5" aria-label="Pipeline stages">
        {stages.filter((s) => s.phase === "online").map((stage, i, list) => (
          <li key={stage.stage_id} className={stage.group ? "border-l-2 border-primary/30 pl-2" : undefined}>
            {groupStartsAt(list, i) && <p className="px-1 pt-1 text-[11px] font-semibold uppercase tracking-wide text-primary">{groupStartsAt(list, i)}</p>}
            {stage.implemented ? <StageTraceCard stage={stage} record={live.stages[stage.stage_id]} /> : <DisabledStage stage={stage} />}
          </li>
        ))}
      </ol>
    </div>
  );
}
