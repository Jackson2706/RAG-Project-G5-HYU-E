import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Workspace } from "@/components/layout/Workspace";
import { DisabledStage } from "@/components/pipeline/DisabledStage";
import { ExecutionTab } from "@/components/pipeline/ExecutionTab";
import { StageConfigCard } from "@/components/pipeline/StageConfigCard";
import { TooltipProvider } from "@/components/ui/primitives";
import { applyEvent, type ChatState, type LiveTrace } from "@/hooks/useChat";
import { defaultChoices, type PipelineConfigState } from "@/hooks/usePipelineConfig";
import type { SystemState } from "@/hooks/useSystem";
import { parseEvents } from "@/services/api";
import type { MethodDef, StageDef, StageRecord } from "@/types/api";

// A small registry in the same shape as GET /api/pipeline/registry.
const topK = { type: "integer", default: 5, label: "Top K", description: "How many chunks.", ui: "slider", min: 1, max: 20, step: null, options: null, scope: "runtime" } as const;
const dense: StageDef = {
  stage_id: "dense_retrieval", name: "Dense Retrieval", phase: "online", description: "Find similar chunks.", base_class: "BaseDenseRetriever",
  optional: true, default_method: "qdrant_cosine", implemented: true,
  methods: [
    { method_id: "qdrant_cosine", name: "Qdrant cosine", description: "Nearest vectors.", implemented: true, class_name: "QdrantDenseRetriever", parameters: { top_k: topK } },
    { method_id: "other_dense", name: "Other dense", description: "Planned.", implemented: false, class_name: "OtherDenseRetriever", parameters: {} },
  ],
};
const reranking: StageDef = {
  stage_id: "reranking", name: "Reranking", phase: "online", description: "Put the best evidence first.", base_class: "BaseReranker",
  optional: true, default_method: null, implemented: false,
  methods: [{ method_id: "cross_encoder", name: "Cross-encoder", description: "", implemented: false, class_name: "CrossEncoderReranker", parameters: {} }],
};
const system = { models: [], defaultModel: null, health: null, refresh: vi.fn() } as unknown as SystemState;

function configFor(stages: StageDef[], errors: PipelineConfigState["errors"] = []) {
  return { stages, choices: defaultChoices(stages), errors, valid: errors.length === 0, setMethod: vi.fn(), setParam: vi.fn(), resetStage: vi.fn(), resetAll: vi.fn() } as unknown as PipelineConfigState;
}

const record = (over: Partial<StageRecord>): StageRecord => ({
  stage_id: "dense_retrieval", name: "Dense Retrieval", method_id: "qdrant_cosine", method_name: "Qdrant cosine", status: "completed",
  input: { query: "How?" }, params: { top_k: 2 }, output: { candidates: [{ rank: 1, chunk_id: "abc12345", doc_id: "d1", score: 0.8123 }], details: {} },
  summary: "1 candidates", duration_ms: 12.4, error: null, ...over,
});

describe("streaming", () => {
  it("parses complete SSE events and keeps the unfinished rest", () => {
    const { events, rest } = parseEvents('data: {"type":"answer_delta","request_id":"r","text":"Hi"}\n\ndata: {"type":"sta');
    expect(events).toEqual([{ type: "answer_delta", request_id: "r", text: "Hi" }]);
    expect(rest).toBe('data: {"type":"sta');
  });

  it("builds the live trace from stage events", () => {
    let t: LiveTrace = { requestId: "r", question: "q", status: "running", stages: {} };
    t = applyEvent(t, { type: "stage", request_id: "r", stage: record({ status: "running" }) });
    t = applyEvent(t, { type: "stage", request_id: "r", stage: record({}) });
    expect(t.stages.dense_retrieval.status).toBe("completed");
  });
});

describe("Configuration tab (driven by the registry)", () => {
  it("lets you select implemented methods and shows planned ones disabled", () => {
    render(<TooltipProvider><StageConfigCard stage={dense} config={configFor([dense])} system={system} /></TooltipProvider>);
    const select = screen.getByLabelText("Method") as HTMLSelectElement;
    const options = Object.fromEntries(Array.from(select.options).map((o) => [o.value, o]));
    expect(options.qdrant_cosine.disabled).toBe(false);
    expect(options.other_dense.disabled).toBe(true);
    expect(options.other_dense.textContent).toContain("not implemented");
    expect(options.__off__.textContent).toContain("Off"); // optional stage can be switched off
  });

  it("draws hyperparameters from the registry and sends changes to the config", () => {
    const config = configFor([dense], [{ stage_id: "dense_retrieval", param: "top_k", message: "Top K must be at most 20" }]);
    render(<TooltipProvider><StageConfigCard stage={dense} config={config} system={system} /></TooltipProvider>);
    expect(screen.getByRole("alert")).toHaveTextContent("at most 20");
    fireEvent.change(screen.getByLabelText("Top K", { selector: "input" }), { target: { value: "7" } });
    expect(config.setParam).toHaveBeenCalledWith("dense_retrieval", "top_k", 7);
  });

  it("shows a newly registered method without any frontend change", () => {
    const added: MethodDef = { method_id: "keyword_overlap", name: "Keyword overlap", description: "New!", implemented: true, class_name: "KeywordOverlapRetriever", parameters: {} };
    const stage = { ...dense, methods: [...dense.methods, added] };
    render(<TooltipProvider><StageConfigCard stage={stage} config={configFor([stage])} system={system} /></TooltipProvider>);
    const option = screen.getByRole("option", { name: "Keyword overlap" }) as HTMLOptionElement;
    expect(option.disabled).toBe(false);
  });

  it("darkens and disables blocks without an implemented method", () => {
    render(<DisabledStage stage={reranking} />);
    const block = screen.getByTestId("disabled-stage-reranking");
    expect(block).toHaveAttribute("aria-disabled", "true");
    expect(block.className).toContain("pointer-events-none");
    expect(block).toHaveTextContent("Not implemented");
    expect(screen.getByRole("combobox")).toBeDisabled();
    expect(block.querySelector("button, a, input, summary, details, [tabindex]")).toBeNull();
  });
});

describe("Execution tab", () => {
  it("shows the method and parameters that really ran; future blocks stay disabled", () => {
    const chat = { messages: [{ id: "m", role: "assistant", content: "", requestId: "r1" }], selected: "r1", select: vi.fn(),
      traces: { r1: { requestId: "r1", question: "How?", status: "completed", stages: { dense_retrieval: record({}) } } } } as unknown as ChatState;  // prettier-ignore
    render(<TooltipProvider><ExecutionTab stages={[dense, reranking]} chat={chat} /></TooltipProvider>);
    const card = screen.getByTestId("stage-dense_retrieval");
    expect(card).toHaveTextContent("Qdrant cosine");
    fireEvent.click(card.querySelector("summary")!);
    expect(screen.getByText("similarity 0.8123")).toBeInTheDocument();
    expect(screen.getByTestId("disabled-stage-reranking")).toBeInTheDocument();
    expect(screen.queryByTestId("stage-reranking")).toBeNull();
  });
});

describe("resizable layout", () => {
  it("has a keyboard-focusable divider on wide screens", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() });
    render(<Workspace mobileView="chat" pipeline={<div>pipeline</div>} chat={<div>chat</div>} />);
    expect(screen.getByRole("separator")).toHaveAttribute("tabindex", "0");
  });

  it("shows one panel at a time on phones", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() });
    render(<Workspace mobileView="pipeline" pipeline={<div>pipeline</div>} chat={<div>chat</div>} />);
    expect(screen.queryByText("chat")).toBeNull();
  });
});
