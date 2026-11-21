import { useCallback, useRef, useState } from "react";

import { newId } from "@/lib/utils";
import { api, streamChat } from "@/services/api";
import type { ClarifyMarker, DemoCase, StageChoices, StageRecord, StreamEvent, Trace } from "@/types/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  requestId?: string; // links an answer to its execution trace
  status?: "streaming" | "done" | "error" | "cancelled";
  trace?: Trace; // final trace (answer, outcome, sources)
  error?: string;
  runs?: CompareRun[]; // compare mode: one column per preset, run one after another
}

/** One preset's answer in compare mode. */
export interface CompareRun {
  presetId: string;
  name: string;
  content: string;
  status: "queued" | "streaming" | "done" | "error" | "cancelled";
  requestId?: string;
  trace?: Trace;
  error?: string;
}

type Run = Pick<CompareRun, "content" | "status" | "requestId" | "trace" | "error">;

/** Earlier user turns of this chat, oldest first: AAES reads them as remembered profile facts. */
export function historyOf(messages: ChatMessage[]): string[] {
  return messages.filter((m) => m.role === "user").map((m) => m.content);
}

/** The clarify marker of the last reply (the column of `presetId` in compare mode), sent back with the next message. */
export function lastClarify(messages: ChatMessage[], presetId?: string): ClarifyMarker | null {
  const last = [...messages].reverse().find((m) => m.role === "assistant");
  const trace = presetId === undefined ? last?.trace : last?.runs?.find((r) => r.presetId === presetId)?.trace;
  return trace?.clarify ?? null;
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
  const latest = useRef<ChatMessage[]>([]);
  latest.current = messages;
  const [forgotAt, setForgotAt] = useState(0); // "Forget my details": turns before this message index are no longer sent as history
  const forgot = useRef(0);
  forgot.current = forgotAt;

  const patch = (id: string, change: Partial<ChatMessage> | ((m: ChatMessage) => Partial<ChatMessage>)) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...(typeof change === "function" ? change(m) : change) } : m)));

  /** Stream one request; `update` writes into the message (chat) or into one compare column. */
  const stream = async (question: string, config: StageChoices, indexId: string, history: string[], signal: AbortSignal,
                        update: (change: Partial<Run> | ((r: Run) => Partial<Run>)) => void, demoCaseId: string | null,
                        followup: ClarifyMarker | null = null) => {
    try {
      await streamChat(question, config, indexId, (event) => {
        if (event.type === "started") {
          const requestId = event.request_id;
          setTraces((t) => ({ ...t, [requestId]: { requestId, question, status: "running", stages: {} } }));
          setSelected(requestId);
          update({ requestId, status: "streaming" });
          return;
        }
        setTraces((t) => ({ ...t, [event.request_id]: applyEvent(t[event.request_id], event) }));
        if (event.type === "answer_delta") update((r) => ({ content: r.content + event.text }));
        if (event.type === "done") {
          const ok = event.trace.status === "completed";
          update({ content: event.trace.answer, trace: event.trace, status: ok ? "done" : "error", error: event.trace.error ?? undefined });
        }
      }, signal, history, demoCaseId, followup);
    } catch (err) {
      update({ status: signal.aborted ? "cancelled" : "error", error: signal.aborted ? undefined : (err as Error).message });
    }
  };

  /** A demo case sends its own session history and id (the oracle presets read the case's labels). */
  const send = useCallback(async (question: string, config: StageChoices, indexId = "default", demo: DemoCase | null = null) => {
    const answerId = newId();
    const history = demo ? demo.history : historyOf(latest.current.slice(forgot.current));
    const followup = demo ? null : lastClarify(latest.current.slice(forgot.current)); // "Forget my details" drops the marker too
    setMessages((ms) => [...ms, { id: newId(), role: "user", content: question }, { id: answerId, role: "assistant", content: "", status: "streaming" }]);
    const controller = new AbortController();
    abort.current = controller;
    setBusy(true);
    await stream(question, config, indexId, history, controller.signal, (change) => patch(answerId, (m) => (typeof change === "function" ? change(m as Run) : change) as Partial<ChatMessage>), demo?.case_id ?? null, followup);
    setBusy(false);
  }, []);

  /** Compare mode: the same question through 2-4 presets, sequentially (the Mac has 16 GB). */
  const sendCompare = useCallback(async (question: string, presets: { id: string; name: string; config: StageChoices }[], indexId = "default",
                                         demo: DemoCase | null = null) => {
    const answerId = newId();
    const history = demo ? demo.history : historyOf(latest.current.slice(forgot.current));
    const followups = presets.map((p) => (demo ? null : lastClarify(latest.current.slice(forgot.current), p.id)));
    const runs: CompareRun[] = presets.map((p) => ({ presetId: p.id, name: p.name, content: "", status: "queued" }));
    setMessages((ms) => [...ms, { id: newId(), role: "user", content: question }, { id: answerId, role: "assistant", content: "", status: "streaming", runs }]);
    const controller = new AbortController();
    abort.current = controller;
    setBusy(true);
    for (const [i, preset] of presets.entries()) {
      const update = (change: Partial<Run> | ((r: Run) => Partial<Run>)) =>
        patch(answerId, (m) => ({ runs: m.runs!.map((r, j) => (j === i ? { ...r, ...(typeof change === "function" ? change(r) : change) } : r)) }));
      if (controller.signal.aborted) update({ status: "cancelled" });
      else await stream(question, preset.config, indexId, history, controller.signal, update, demo?.case_id ?? null, followups[i]);
    }
    patch(answerId, { status: controller.signal.aborted ? "cancelled" : "done" });
    setBusy(false);
  }, []);

  const cancel = useCallback(() => abort.current?.abort(), []);

  const reset = useCallback(() => {
    setMessages([]);
    setSelected(null);
    setForgotAt(0);
  }, []);

  /** Keep the conversation on screen, but stop sending earlier turns, so nothing said about the student is remembered. */
  const forget = useCallback(() => setForgotAt(latest.current.length), []);
  const remembered = historyOf(messages.slice(forgotAt));

  /** Show a request in the Execution tab (loads it from the backend if it is not in memory). */
  const select = useCallback(async (requestId: string) => {
    setSelected(requestId);
    if (traces[requestId]) return;
    const trace = await api.trace(requestId).catch(() => null);
    if (trace) setTraces((t) => ({ ...t, [requestId]: applyEvent({ requestId, question: trace.question, status: trace.status, stages: {} }, { type: "done", request_id: requestId, trace }) }));
  }, [traces]);

  return { messages, traces, selected, select, send, sendCompare, cancel, reset, forget, remembered, busy };
}

export type ChatState = ReturnType<typeof useChat>;
