import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/chat/ChatPanel";
import { Header } from "@/components/layout/Header";
import { Workspace } from "@/components/layout/Workspace";
import { PipelinePanel, type PipelineTab } from "@/components/pipeline/PipelinePanel";
import { TooltipProvider } from "@/components/ui/primitives";
import { useChat } from "@/hooks/useChat";
import { usePipelineConfig } from "@/hooks/usePipelineConfig";
import { useSystem } from "@/hooks/useSystem";
import { storage } from "@/lib/utils";

export default function App() {
  const config = usePipelineConfig();
  const system = useSystem();
  const chat = useChat();
  const [tab, setTab] = useState<PipelineTab>("configuration");
  const [mobileView, setMobileView] = useState<"chat" | "pipeline">("chat");
  const [dark, setDark] = useState(() => storage.get<boolean | null>("hyu-compass:dark", null) ?? window.matchMedia("(prefers-color-scheme: dark)").matches);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    storage.set("hyu-compass:dark", dark);
  }, [dark]);

  const blocked = !config.choices ? "Loading the pipeline configuration…" : !config.valid ? "Fix the configuration error in the RAG Pipeline panel first." : null;

  const send = (question: string) => {
    setTab("execution"); // watch the stages run
    void chat.send(question, config.choices!); // the exact methods + parameters for this request
  };

  const inspect = (requestId: string) => {
    void chat.select(requestId);
    setTab("execution");
    setMobileView("pipeline");
  };

  return (
    <TooltipProvider>
      <div className="flex h-full flex-col">
        <Header system={system} dark={dark} onToggleTheme={() => setDark(!dark)} mobileView={mobileView} onMobileView={setMobileView} />
        <Workspace
          mobileView={mobileView}
          pipeline={<PipelinePanel config={config} system={system} chat={chat} tab={tab} onTabChange={setTab} />}
          chat={<ChatPanel chat={chat} onSend={send} blockedReason={blocked} onInspect={inspect} />}
        />
      </div>
    </TooltipProvider>
  );
}
