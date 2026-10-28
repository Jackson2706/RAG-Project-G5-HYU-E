import { ArrowUp, Compass, History, Plus, Square, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { MessageItem } from "@/components/chat/MessageItem";
import { Button, IconButton } from "@/components/ui/primitives";
import type { ChatState } from "@/hooks/useChat";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "How many credits can a first-year student register for?",
  "What documents do I need for the need-based scholarship?",
  "How do international students apply for a dormitory at ERICA?",
  "Where can I find orientation information?",
];

interface Props {
  chat: ChatState;
  onSend: (question: string) => void;
  sendBlockedReason: string | null;
  onInspect: (requestId: string) => void;
}

export function ChatPanel({ chat, onSend, sendBlockedReason, onInspect }: Props) {
  const [text, setText] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messages = chat.active.messages;
  const last = messages[messages.length - 1];

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, last?.content]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const submit = (q = text) => {
    if (!q.trim() || chat.busy || sendBlockedReason) return;
    onSend(q);
    setText("");
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <h2 className="truncate text-sm font-semibold">{chat.active.messages.length ? chat.active.title : "Chat"}</h2>
        <div className="flex items-center gap-1">
          <IconButton label="Previous conversations" onClick={() => setShowHistory(!showHistory)} aria-expanded={showHistory}>
            <History className="h-4 w-4" />
          </IconButton>
          <Button size="sm" variant="outline" onClick={chat.newConversation} disabled={chat.busy} aria-label="New chat"><Plus className="h-3.5 w-3.5" /><span className="hidden sm:inline">New chat</span></Button>
        </div>
      </div>

      {showHistory && (
        <nav aria-label="Conversations" className="max-h-56 overflow-y-auto border-b border-border bg-surface p-2">
          <ul className="space-y-0.5">
            {chat.conversations.filter((c) => c.messages.length).map((c) => (
              <li key={c.id} className="flex items-center gap-1">
                <button type="button" onClick={() => { chat.setActiveId(c.id); setShowHistory(false); }}
                        className={cn("min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted", c.id === chat.active.id && "bg-muted font-medium")}>
                  {c.title}
                  <span className="ml-2 text-[11px] text-muted-foreground">{new Date(c.createdAt).toLocaleDateString()}</span>
                </button>
                <IconButton label={`Delete “${c.title}”`} onClick={() => chat.deleteConversation(c.id)} disabled={chat.busy}><Trash2 className="h-3.5 w-3.5" /></IconButton>
              </li>
            ))}
            {!chat.conversations.some((c) => c.messages.length) && <li className="px-2 py-1 text-xs text-muted-foreground">No previous conversations.</li>}
          </ul>
        </nav>
      )}

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto" aria-live="polite">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center gap-5 pt-[8vh] text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent"><Compass className="h-6 w-6 text-primary" /></div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">How can I help you find your way?</h1>
                <p className="mt-1 text-sm text-muted-foreground">Answers come only from the indexed HYU documents, with sources you can check.</p>
              </div>
              <div className="grid w-full gap-2 sm:grid-cols-2">
                {EXAMPLES.map((q) => (
                  <button key={q} type="button" onClick={() => submit(q)} disabled={chat.busy || !!sendBlockedReason}
                          className="rounded-xl border border-border bg-card px-3.5 py-3 text-left text-sm transition-colors hover:bg-muted disabled:opacity-50">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => <MessageItem key={m.id} message={m} onInspect={onInspect} selected={!!m.requestId && m.requestId === chat.selectedRequestId} />)
          )}
        </div>
      </div>

      <div className="border-t border-border bg-background px-4 pb-4 pt-3">
        <form className="mx-auto max-w-3xl" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <div className="flex items-end gap-2 rounded-2xl border border-border bg-card px-3 py-2 shadow-sm focus-within:border-primary/70 focus-within:ring-2 focus-within:ring-ring/30">
            <label htmlFor="chat-input" className="sr-only">Ask a question</label>
            <textarea
              id="chat-input"
              ref={inputRef}
              rows={1}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder="Ask about orientation, registration, scholarships…"
              maxLength={2000}
              className="max-h-[200px] min-h-[24px] flex-1 resize-none bg-transparent py-1 text-[15px] outline-none placeholder:text-muted-foreground focus-visible:outline-none"
            />
            {chat.busy ? (
              <Button variant="primary" size="icon" aria-label="Stop generating" onClick={chat.cancel} className="rounded-full"><Square className="h-3.5 w-3.5" /></Button>
            ) : (
              <Button type="submit" variant="primary" size="icon" aria-label="Send message" disabled={!text.trim() || !!sendBlockedReason} className="rounded-full">
                <ArrowUp className="h-4 w-4" />
              </Button>
            )}
          </div>
          <p className={cn("mt-1.5 text-center text-[11px]", sendBlockedReason ? "text-danger" : "text-muted-foreground")}>
            {sendBlockedReason ?? "Enter to send · Shift+Enter for a new line · Answers can be wrong — check the cited sources."}
          </p>
        </form>
      </div>
    </div>
  );
}
