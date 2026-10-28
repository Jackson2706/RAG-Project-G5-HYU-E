// Two resizable panels (RAG Pipeline | Chat). Drag the divider to resize, double-click it to
// reset, or focus it and use the arrow keys. The layout is persisted in localStorage.
// Below the md breakpoint only one panel is shown at a time (toggle in the header).
import type { ReactNode } from "react";
import { Group, Panel, Separator, useDefaultLayout } from "react-resizable-panels";

import { useMediaQuery } from "@/hooks/useMediaQuery";

export function Workspace({ pipeline, chat, mobileView }: { pipeline: ReactNode; chat: ReactNode; mobileView: "chat" | "pipeline" }) {
  const desktop = useMediaQuery("(min-width: 768px)");
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({ id: "hyu-compass-layout", storage: localStorageSafe });

  if (!desktop) {
    return <main className="min-h-0 flex-1 overflow-hidden">{mobileView === "chat" ? chat : pipeline}</main>;
  }
  return (
    <Group orientation="horizontal" defaultLayout={defaultLayout} onLayoutChanged={onLayoutChanged} className="min-h-0 flex-1">
      <Panel id="pipeline" defaultSize="38" minSize="300px" maxSize="70" className="bg-surface">
        <aside aria-label="RAG pipeline" className="h-full overflow-hidden">{pipeline}</aside>
      </Panel>
      <Separator aria-label="Resize panels (double-click to reset)" />
      <Panel id="chat" minSize="360px">
        <main className="h-full overflow-hidden">{chat}</main>
      </Panel>
    </Group>
  );
}

const localStorageSafe = {
  getItem: (k: string) => {
    try {
      return localStorage.getItem(k);
    } catch {
      return null;
    }
  },
  setItem: (k: string, v: string) => {
    try {
      localStorage.setItem(k, v);
    } catch {
      /* not persisted */
    }
  },
};
