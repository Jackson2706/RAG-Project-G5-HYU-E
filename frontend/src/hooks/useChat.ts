import { useCallback, useEffect, useRef, useState } from "react";

import { newId, storage } from "@/lib/utils";
import { api, streamChat } from "@/services/api";
import type { AnswerResult, ExecutionTrace, PipelineConfig, PipelineEvent, StageTrace } from "@/types/api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  requestId?: string;
  status?: "streaming" | "done" | "error" | "cancelled";
  result?: AnswerResult;
  error?: string;
  createdAt: string;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  messages: ChatMessage[];
}

export interface LiveTrace {
  request_id: string;
  question: string;
  status: ExecutionTrace["status"];
  stages: Record<string, StageTrace>;
  trace?: ExecutionTrace; // final trace from the backend
  config_hash?: string;
  index_revision?: Record<string, unknown>;
}

const CONVERSATIONS_KEY = "hyu-compass:conversations";
const MAX_CONVERSATIONS = 30;

function emptyConversation(): Conversation {
  return { id: newId(), title: "New conversation", createdAt: new Date().toISOString(), messages: [] };
}

/** Pure reducer for one streamed event → live trace. Exported for tests. */
export function applyEvent(trace: LiveTrace, event: PipelineEvent): LiveTrace {
  switch (event.type) {
    case "pipeline_started":
      return { ...trace, status: "running", config_hash: event.data?.config_hash as string, index_revision: event.data?.index_revision as Record<string, unknown> };
    case "stage_started":
    case "stage_completed":
    case "stage_bypassed":
    case "stage_failed":
      return event.stage ? { ...trace, stages: { ...trace.stages, [event.stage.stage_id]: event.stage } } : trace;
    case "pipeline_completed":
    case "pipeline_error": {
      const final = event.trace;
      if (!final) return { ...trace, status: "failed" };
      return { ...trace, status: final.status, trace: final, stages: Object.fromEntries(final.stages.map((s) => [s.stage_id, s])) };
    }
    default:
      return trace;
  }
}

export function traceFromExecution(t: ExecutionTrace): LiveTrace {
  return { request_id: t.request_id, question: t.question, status: t.status, trace: t, config_hash: t.config.config_hash,
           index_revision: t.index_revision, stages: Object.fromEntries(t.stages.map((s) => [s.stage_id, s])) };  // prettier-ignore
}

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    const saved = storage.get<Conversation[]>(CONVERSATIONS_KEY, []);
    return saved.length ? saved : [emptyConversation()];
  });
  const [activeId, setActiveId] = useState<string>(() => conversations[0].id);
  const [traces, setTraces] = useState<Record<string, LiveTrace>>({});
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Persist conversations (messages only; traces stay in MongoDB and are fetched on demand).
    const finished = conversations.map((c) => ({
      ...c,
      messages: c.messages.map((m) => (m.status === "streaming" ? { ...m, status: "cancelled" as const } : m)),
    }));
    storage.set(CONVERSATIONS_KEY, finished.slice(0, MAX_CONVERSATIONS));
  }, [conversations]);

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0];

  const updateMessage = useCallback((convId: string, msgId: string, patch: (m: ChatMessage) => ChatMessage) => {
    setConversations((cs) => cs.map((c) => (c.id !== convId ? c : { ...c, messages: c.messages.map((m) => (m.id === msgId ? patch(m) : m)) })));
  }, []);

  const send = useCallback(
    async (question: string, config: PipelineConfig) => {
      if (busy || !question.trim()) return;
      const convId = active.id;
      const now = new Date().toISOString();
      const userMsg: ChatMessage = { id: newId(), role: "user", content: question.trim(), createdAt: now };
      const botMsg: ChatMessage = { id: newId(), role: "assistant", content: "", status: "streaming", createdAt: now };
      setConversations((cs) =>
        cs.map((c) =>
          c.id !== convId ? c : { ...c, title: c.messages.length ? c.title : question.trim().slice(0, 60), messages: [...c.messages, userMsg, botMsg] },
        ),
      );
      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);
      let requestId: string | null = null;
      try {
        await streamChat(
          { question: question.trim(), session_id: convId, config },
          (event) => {
            if (!requestId) {
              requestId = event.request_id;
              const rid = requestId;
              setTraces((t) => ({ ...t, [rid]: { request_id: rid, question: question.trim(), status: "running", stages: {} } }));
              setSelectedRequestId(rid);
              updateMessage(convId, botMsg.id, (m) => ({ ...m, requestId: rid }));
            }
            const rid = requestId;
            setTraces((t) => ({ ...t, [rid]: applyEvent(t[rid], event) }));
            if (event.type === "answer_delta" && event.delta) {
              updateMessage(convId, botMsg.id, (m) => ({ ...m, content: m.content + event.delta }));
            } else if (event.type === "answer_completed" && event.result) {
              const result = event.result;
              updateMessage(convId, botMsg.id, (m) => ({ ...m, content: result.answer, result }));
            } else if (event.type === "pipeline_completed") {
              updateMessage(convId, botMsg.id, (m) => ({ ...m, status: "done" }));
            } else if (event.type === "pipeline_error") {
              updateMessage(convId, botMsg.id, (m) => ({ ...m, status: "error", error: event.error ?? "Pipeline failed" }));
            }
          },
          controller.signal,
        );
        updateMessage(convId, botMsg.id, (m) => (m.status === "streaming" ? { ...m, status: "error", error: "The stream ended unexpectedly." } : m));
      } catch (err) {
        const aborted = controller.signal.aborted;
        updateMessage(convId, botMsg.id, (m) => ({ ...m, status: aborted ? "cancelled" : "error", error: aborted ? undefined : (err as Error).message }));
        if (aborted && requestId) {
          const rid = requestId;
          setTraces((t) => ({ ...t, [rid]: { ...t[rid], status: "cancelled" } }));
        }
      } finally {
        setBusy(false);
        abortRef.current = null;
      }
    },
    [active.id, busy, updateMessage],
  );

  const cancel = useCallback(() => abortRef.current?.abort(), []);

  const newConversation = useCallback(() => {
    const conv = emptyConversation();
    setConversations((cs) => [conv, ...cs.filter((c) => c.messages.length)]);
    setActiveId(conv.id);
    setSelectedRequestId(null);
  }, []);

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((cs) => {
        const rest = cs.filter((c) => c.id !== id);
        const next = rest.length ? rest : [emptyConversation()];
        if (id === activeId) setActiveId(next[0].id);
        return next;
      });
    },
    [activeId],
  );

  /** Select a request's trace; loads it from the backend if it is not in memory (e.g. after reload). */
  const selectRequest = useCallback(
    async (requestId: string) => {
      setSelectedRequestId(requestId);
      if (traces[requestId]?.trace || traces[requestId]?.status === "running") return;
      try {
        const t = await api.trace(requestId);
        setTraces((all) => ({ ...all, [requestId]: traceFromExecution(t) }));
      } catch {
        /* trace not stored (e.g. database reset); the Execution tab shows an empty state */
      }
    },
    [traces],
  );

  return { conversations, active, setActiveId, send, cancel, busy, traces, selectedRequestId, selectRequest, newConversation, deleteConversation };
}

export type ChatState = ReturnType<typeof useChat>;
