import { useCallback, useRef, useState } from "react";

import { newId } from "@/lib/utils";
import { api, streamChat } from "@/services/api";
import type { StageChoices, StageRecord, StreamEvent, Trace } from "@/types/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  requestId?: string; // links an answer to its execution trace
  status?: "streaming" | "done" | "error" | "cancelled";
  trace?: Trace; // final trace (answer, outcome, citations)
  error?: string;
}

/** Live state of one request while it runs: stages arrive one by one. */
export interface LiveTrace {
  requestId: string;
  question: string;
  status: Trace["status"];
  stages: Record<string, StageRecord>;
  final?: Trace;
}

/** Update a live trace with one stream event. Kept pure so it can be unit-tested. */
export function applyEvent(trace: LiveTrace, event: StreamEvent): LiveTrace {
  if (event.type === "stage") return { ...trace, stages: { ...trace.stages, [event.stage.stage_id]: event.stage } };
  if (event.type === "done") {
    const stages = Object.fromEntries(event.trace.stages.map((s) => [s.stage_id, s]));
    return { ...trace, status: event.trace.status, stages, final: event.trace };
  }
  return trace;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [traces, setTraces] = useState<Record<string, LiveTrace>>({});
  const [selected, setSelected] = useState<string | null>(null); // request shown in the Execution tab
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const patch = (id: string, change: Partial<ChatMessage> | ((m: ChatMessage) => Partial<ChatMessage>)) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...(typeof change === "function" ? change(m) : change) } : m)));

  const send = useCallback(async (question: string, config: StageChoices) => {
    const answerId = newId();
    setMessages((ms) => [...ms, { id: newId(), role: "user", content: question }, { id: answerId, role: "assistant", content: "", status: "streaming" }]);
    const controller = new AbortController();
    abort.current = controller;
    setBusy(true);
    let requestId = "";
    try {
      await streamChat(question, config, (event) => {
        if (event.type === "started") {
          requestId = event.request_id;
          setTraces((t) => ({ ...t, [requestId]: { requestId, question, status: "running", stages: {} } }));
          setSelected(requestId);
          patch(answerId, { requestId });
          return;
        }
        setTraces((t) => ({ ...t, [event.request_id]: applyEvent(t[event.request_id], event) }));
        if (event.type === "answer_delta") patch(answerId, (m) => ({ content: m.content + event.text }));
        if (event.type === "done") {
          const ok = event.trace.status === "completed";
          patch(answerId, { content: event.trace.answer, trace: event.trace, status: ok ? "done" : "error", error: event.trace.error ?? undefined });
        }
      }, controller.signal);
    } catch (err) {
      const cancelled = controller.signal.aborted;
      patch(answerId, { status: cancelled ? "cancelled" : "error", error: cancelled ? undefined : (err as Error).message });
    } finally {
      setBusy(false);
    }
  }, []);

  const cancel = useCallback(() => abort.current?.abort(), []);

  const reset = useCallback(() => {
    setMessages([]);
    setSelected(null);
  }, []);

  /** Show a request in the Execution tab (loads it from the backend if it is not in memory). */
  const select = useCallback(async (requestId: string) => {
    setSelected(requestId);
    if (traces[requestId]) return;
    const trace = await api.trace(requestId).catch(() => null);
    if (trace) setTraces((t) => ({ ...t, [requestId]: applyEvent({ requestId, question: trace.question, status: trace.status, stages: {} }, { type: "done", request_id: requestId, trace }) }));
  }, [traces]);

  return { messages, traces, selected, select, send, cancel, reset, busy };
}

export type ChatState = ReturnType<typeof useChat>;
