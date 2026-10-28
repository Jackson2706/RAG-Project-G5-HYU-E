import { useCallback, useEffect, useState } from "react";

import { ChatPanel } from "@/components/chat/ChatPanel";
import { IndexDialog } from "@/components/documents/IndexDialog";
import { Header } from "@/components/layout/Header";
import { Workspace } from "@/components/layout/Workspace";
import { PipelinePanel, type PipelineTab } from "@/components/pipeline/PipelinePanel";
import { TooltipProvider } from "@/components/ui/primitives";
import { useChat } from "@/hooks/useChat";
import { usePipelineConfig } from "@/hooks/usePipelineConfig";
import { useSystem } from "@/hooks/useSystem";
import { onlineConfig } from "@/lib/config";
import { storage } from "@/lib/utils";

const THEME_KEY = "hyu-compass:theme";

export default function App() {
  const cfg = usePipelineConfig();
  const chat = useChat();
  const system = useSystem();
  const [tab, setTab] = useState<PipelineTab>("configuration");
  const [mobileView, setMobileView] = useState<"chat" | "pipeline">("chat");
  const [indexOpen, setIndexOpen] = useState(false);
  const [dark, setDark] = useState(() => storage.get<boolean | null>(THEME_KEY, null) ?? window.matchMedia("(prefers-color-scheme: dark)").matches);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  // The chat sends the validated online configuration; invalid drafts block sending.
  const blocked = !cfg.registry || !cfg.draft
    ? "Loading pipeline configuration…"
    : cfg.validation && !cfg.validation.valid
      ? `Fix ${cfg.validation.errors.length} configuration error(s) in the RAG Pipeline panel before sending.`
      : null;

  const send = useCallback(
    (q: string) => {
      if (!cfg.registry || !cfg.draft) return;
      setTab("execution");
      void chat.send(q, onlineConfig(cfg.registry, cfg.draft));
    },
    [cfg.registry, cfg.draft, chat],
  );

  const inspect = useCallback(
    (requestId: string) => {
      void chat.selectRequest(requestId);
      setTab("execution");
      setMobileView("pipeline");
    },
    [chat],
  );

  return (
    <TooltipProvider>
      <div className="flex h-full flex-col">
        <Header system={system} dark={dark} onToggleTheme={() => { setDark(!dark); storage.set(THEME_KEY, !dark); }}
                onOpenIndex={() => setIndexOpen(true)} mobileView={mobileView} onMobileView={setMobileView} />
        <Workspace
          mobileView={mobileView}
          pipeline={<PipelinePanel cfg={cfg} chat={chat} system={system} tab={tab} onTabChange={setTab} />}
          chat={<ChatPanel chat={chat} onSend={send} sendBlockedReason={blocked} onInspect={inspect} />}
        />
        <IndexDialog open={indexOpen} onOpenChange={setIndexOpen} cfg={cfg} system={system} />
      </div>
    </TooltipProvider>
  );
}
