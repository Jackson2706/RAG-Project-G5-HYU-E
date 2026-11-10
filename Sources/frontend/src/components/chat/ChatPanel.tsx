import { ArrowUp, Compass, Plus, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { MessageItem } from "@/components/chat/MessageItem";
import { Button } from "@/components/ui/primitives";
import type { ChatState } from "@/hooks/useChat";

const EXAMPLES = [
  "How many credits can a first-year student register for?",
  "What documents do I need for the need-based scholarship?",
  "How do I apply for a dormitory at the ERICA campus?",
  "Where can I find orientation information?",
];

export function ChatPanel({ chat, onSend, blockedReason, onInspect }: {
  chat: ChatState; onSend: (q: string) => void; blockedReason: string | null; onInspect: (requestId: string) => void;
}) {
  const [text, setText] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const last = chat.messages[chat.messages.length - 1];

  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight }); }, [chat.messages.length, last?.content]);
  useEffect(() => {
    if (!input.current) return;
    input.current.style.height = "auto";
    input.current.style.height = `${Math.min(input.current.scrollHeight, 200)}px`;
  }, [text]);

  const submit = (q = text) => {
    if (!q.trim() || chat.busy || blockedReason) return;
    onSend(q.trim());
    setText("");
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <h2 className="text-sm font-semibold">Chat</h2>
        <Button size="sm" onClick={chat.reset} disabled={chat.busy} aria-label="New conversation">
          <Plus className="h-3.5 w-3.5" /><span className="hidden sm:inline">New conversation</span>
        </Button>
      </div>

      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto" aria-live="polite">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {chat.messages.length === 0 ? (
            <div className="flex flex-col items-center gap-5 pt-[8vh] text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent"><Compass className="h-6 w-6 text-primary" /></div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">How can I help you find your way?</h1>
                <p className="mt-1 text-sm text-muted-foreground">Answers come only from the indexed HYU documents, with sources.</p>
              </div>
              <div className="grid w-full gap-2 sm:grid-cols-2">
                {EXAMPLES.map((q) => (
                  <button key={q} type="button" onClick={() => submit(q)} disabled={chat.busy || !!blockedReason}
                          className="rounded-xl border border-border bg-card px-3.5 py-3 text-left text-sm transition-colors hover:bg-muted disabled:opacity-50">{q}</button>
                ))}
              </div>
            </div>
          ) : (
            chat.messages.map((m) => <MessageItem key={m.id} message={m} onInspect={onInspect} />)
          )}
        </div>
      </div>

      <form className="border-t border-border px-4 pb-4 pt-3" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-border bg-card px-3 py-2 focus-within:ring-2 focus-within:ring-ring/30">
          <label htmlFor="chat-input" className="sr-only">Ask a question</label>
          <textarea id="chat-input" ref={input} rows={1} value={text} maxLength={2000}
                    placeholder="Ask about orientation, registration, scholarships…"
                    className="max-h-[200px] flex-1 resize-none bg-transparent py-1 text-[15px] outline-none placeholder:text-muted-foreground focus-visible:outline-none"
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
                    }} />
          {chat.busy ? (
            <Button variant="primary" size="icon" aria-label="Stop" onClick={chat.cancel} className="rounded-full"><Square className="h-3.5 w-3.5" /></Button>
          ) : (
            <Button type="submit" variant="primary" size="icon" aria-label="Send" disabled={!text.trim() || !!blockedReason} className="rounded-full"><ArrowUp className="h-4 w-4" /></Button>
          )}
        </div>
        <p className={`mt-1.5 text-center text-[11px] ${blockedReason ? "text-danger" : "text-muted-foreground"}`}>
          {blockedReason ?? "Enter to send · Shift+Enter for a new line · Check the sources — answers can be wrong."}
        </p>
      </form>
    </div>
  );
}
