import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";

import { ConfigurationTab } from "@/components/pipeline/ConfigurationTab";
import { ExecutionTab } from "@/components/pipeline/ExecutionTab";
import { Button, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/primitives";
import type { ChatState } from "@/hooks/useChat";
import type { PipelineConfigState } from "@/hooks/usePipelineConfig";
import type { SystemState } from "@/hooks/useSystem";

export type PipelineTab = "configuration" | "execution";

export function PipelinePanel({ cfg, chat, system, tab, onTabChange }: { cfg: PipelineConfigState; chat: ChatState; system: SystemState; tab: PipelineTab; onTabChange: (t: PipelineTab) => void }) {
  if (cfg.loadError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <AlertTriangle className="h-6 w-6 text-danger" />
        <p className="text-sm">Could not load the pipeline registry.</p>
        <p className="text-xs text-muted-foreground">{cfg.loadError}</p>
        <Button size="sm" variant="outline" onClick={() => void cfg.reload()}><RefreshCw className="h-3.5 w-3.5" /> Retry</Button>
      </div>
    );
  }
  if (!cfg.registry || !cfg.draft) {
    return <div className="flex h-full items-center justify-center text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" aria-label="Loading" /></div>;
  }
  return (
    <Tabs value={tab} onValueChange={(v) => onTabChange(v as PipelineTab)} className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <h2 className="text-sm font-semibold">RAG Pipeline</h2>
        <TabsList aria-label="Pipeline view">
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
          <TabsTrigger value="execution">Execution</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="configuration" className="min-h-0 flex-1 overflow-y-auto">
        <ConfigurationTab cfg={cfg} system={system} />
      </TabsContent>
      <TabsContent value="execution" className="min-h-0 flex-1 overflow-y-auto">
        <ExecutionTab registry={cfg.registry} chat={chat} />
      </TabsContent>
    </Tabs>
  );
}
