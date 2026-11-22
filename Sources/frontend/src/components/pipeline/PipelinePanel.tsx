import { ConfigurationTab } from "@/components/pipeline/ConfigurationTab";
import { ExecutionTab } from "@/components/pipeline/ExecutionTab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/primitives";
import type { ChatState } from "@/hooks/useChat";
import type { PipelineConfigState } from "@/hooks/usePipelineConfig";
import type { SystemState } from "@/hooks/useSystem";

export type PipelineTab = "configuration" | "execution";

export function PipelinePanel({ config, system, chat, tab, onTabChange }: {
  config: PipelineConfigState; system: SystemState; chat: ChatState; tab: PipelineTab; onTabChange: (t: PipelineTab) => void;
}) {
  return (
    <Tabs value={tab} onValueChange={(v) => onTabChange(v as PipelineTab)} className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <h2 className="text-sm font-semibold">RAG Pipeline</h2>
        <TabsList aria-label="Pipeline view">
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
          <TabsTrigger value="execution">Execution</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="configuration" className="min-h-0 flex-1 overflow-y-auto"><ConfigurationTab config={config} system={system} /></TabsContent>
      <TabsContent value="execution" className="min-h-0 flex-1 overflow-y-auto"><ExecutionTab stages={config.stages} chat={chat} /></TabsContent>
    </Tabs>
  );
}
