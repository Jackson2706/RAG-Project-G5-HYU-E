import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Workspace } from "@/components/layout/Workspace";
import { ConfigurationTab } from "@/components/pipeline/ConfigurationTab";
import { DisabledStage } from "@/components/pipeline/DisabledStage";
import { ParamControl } from "@/components/pipeline/ParamControl";
import { ExecutionTab } from "@/components/pipeline/ExecutionTab";
import { StageConfigCard } from "@/components/pipeline/StageConfigCard";
import { TooltipProvider } from "@/components/ui/primitives";
import { applyEvent, type ChatState, type LiveTrace } from "@/hooks/useChat";
import { defaultChoices, type PipelineConfigState } from "@/hooks/usePipelineConfig";
import type { SystemState } from "@/hooks/useSystem";
import { parseEvents } from "@/services/api";
import type { IndexRevision, MethodDef, Preset, StageDef, StageRecord } from "@/types/api";

// A small registry in the same shape as GET /api/pipeline/registry.
const topK = { type: "integer", default: 5, label: "Top K", description: "How many chunks.", ui: "slider", min: 1, max: 20, step: null, options: null, scope: "runtime", advanced: false } as const;
const ef = { ...topK, label: "HNSW ef", ui: "number", default: 100, max: 1024, advanced: true } as const;
const dense: StageDef = {
  stage_id: "dense_retrieval", name: "Dense Retrieval", phase: "online", description: "Find similar chunks.", base_class: "BaseDenseRetriever",
  folder: "app/rag/blocks/retrieval/dense_retrieval/", group: "Candidate Retrieval", optional: true, default_method: "qdrant_cosine", implemented: true,
  methods: [
    { method_id: "qdrant_cosine", name: "Qdrant cosine", description: "Nearest vectors.", implemented: true, class_name: "QdrantDenseRetriever", file: "retrieval/dense_retrieval/qdrant_cosine.py", parameters: { top_k: topK } },
    { method_id: "other_dense", name: "Other dense", description: "Planned.", implemented: false, class_name: "OtherDenseRetriever", file: "retrieval/dense_retrieval/other.py", parameters: {} },
  ],
};
const prefilter: StageDef = {
  stage_id: "metadata_prefiltering", name: "Metadata Prefiltering", phase: "online", description: "Restrict the search to eligible documents.",
  base_class: "BaseMetadataPrefilter", folder: "app/rag/blocks/metadata_filtering/metadata_prefiltering/", group: null, optional: true, default_method: null, implemented: false,
  methods: [{ method_id: "qdrant_prefilter", name: "Qdrant payload filter", description: "", implemented: false, class_name: "QdrantMetadataPrefilter", file: "metadata_filtering/metadata_prefiltering/qdrant_prefilter.py", parameters: {} }],
};
const reranking: StageDef = {
  stage_id: "reranking", name: "Reranking", phase: "online", description: "Put the best evidence first.", base_class: "BaseReranker",
  folder: "app/rag/blocks/evidence/reranking/", group: null, optional: true, default_method: null, implemented: false,
  methods: [{ method_id: "cross_encoder", name: "Cross-encoder", description: "", implemented: false, class_name: "CrossEncoderReranker", file: "evidence/reranking/cross_encoder.py", parameters: {} }],
};
const system = { models: [], defaultModel: null, health: null, refresh: vi.fn() } as unknown as SystemState;

function configFor(stages: StageDef[], errors: PipelineConfigState["errors"] = [], extra: Partial<PipelineConfigState> = {}) {
  return { stages, choices: defaultChoices(stages), errors, valid: errors.length === 0, setMethod: vi.fn(), setParam: vi.fn(), resetStage: vi.fn(), resetAll: vi.fn(),
    presets: [], presetId: null, modified: false, applyPreset: vi.fn(), saveCustom: vi.fn(), hasCustom: false, exportJson: vi.fn(), importJson: vi.fn(),
    indexes: [], indexId: "default", selectIndex: vi.fn(), ...extra } as unknown as PipelineConfigState;  // prettier-ignore
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

  it("keeps advanced hyperparameters folded under Advanced settings", () => {
    const stage = { ...dense, methods: [{ ...dense.methods[0], parameters: { top_k: topK, hnsw_ef: ef } }, dense.methods[1]] };
    render(<TooltipProvider><StageConfigCard stage={stage} config={configFor([stage])} system={system} /></TooltipProvider>);
    const advanced = screen.getByTestId("advanced-dense_retrieval");
    expect(advanced).toHaveTextContent("Advanced settings (1)");
    expect(advanced).not.toHaveAttribute("open");
    expect(advanced).toContainElement(screen.getByTestId("param-hnsw_ef"));
    expect(advanced).not.toContainElement(screen.getByTestId("param-top_k"));
  });

  it("offers both backbone LLMs from the installed Ollama models", () => {
    const models = { ...system, models: [{ name: "llama2:7b", parameter_size: "7B", capabilities: [] }, { name: "qwen3.5:4b", parameter_size: "4.5B", capabilities: [] }],
      defaultModel: "llama2:7b" } as unknown as SystemState;  // prettier-ignore
    const onChange = vi.fn();
    const def = { ...topK, type: "string", ui: "ollama_model", default: "", label: "Ollama model" } as const;
    render(<TooltipProvider><ParamControl id="m" name="model" def={def} value="" onChange={onChange} system={models} /></TooltipProvider>);
    fireEvent.change(screen.getByLabelText("Ollama model"), { target: { value: "qwen3.5:4b" } });
    expect(onChange).toHaveBeenCalledWith("qwen3.5:4b");
    expect(screen.getByRole("option", { name: "llama2:7b · 7B" })).toBeInTheDocument();
  });

  it("selects experiment presets and index revisions, and warns when the index was built differently", () => {
    const chunking: StageDef = { ...dense, stage_id: "chunking", name: "Chunking", phase: "offline", group: "Ingestion", optional: false, default_method: "section_tokens",
      methods: [{ ...dense.methods[0], method_id: "section_tokens", name: "Section", parameters: { chunk_size: { ...topK, default: 256, max: 512 } } }] };  // prettier-ignore
    const presets: Preset[] = [
      { id: "B0_BASIC_DENSE_RAG", kind: "baseline", name: "B0 — Basic Dense RAG", description: "The original app.", enabled: true, config: {}, errors: [] },
      { id: "PROPOSED_APPROACH", kind: "proposed", name: "Proposed approach", description: "Reserved.", enabled: false, config: null, errors: [] },
    ];
    const indexes: IndexRevision[] = [
      { index_id: "default", manifest: null, info: { documents: 5, chunks: 23, vectors: 23, chunking: null, embedding_method: "bge_small_en" } },
      { index_id: "scifact_o3", manifest: { config: { chunking: { method: "section_tokens", params: { chunk_size: 128 } } } },
        info: { documents: 5183, chunks: 9000, vectors: 9000, chunking: null, embedding_method: "bge_small_en" } },
    ];  // prettier-ignore
    const config = configFor([dense, chunking], [], { presets, indexes, indexId: "scifact_o3" });
    render(<TooltipProvider><ConfigurationTab config={config} system={system} /></TooltipProvider>);
    fireEvent.change(screen.getByLabelText("Experiment preset"), { target: { value: "B0_BASIC_DENSE_RAG" } });
    expect(config.applyPreset).toHaveBeenCalledWith("B0_BASIC_DENSE_RAG");
    expect((screen.getByRole("option", { name: /Proposed approach/ }) as HTMLOptionElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Index to search"), { target: { value: "default" } });
    expect(config.selectIndex).toHaveBeenCalledWith("default");
    expect(screen.getByText(/Chunking differ from how this index was built/)).toBeInTheDocument();
    expect(screen.getByText(/built by the evaluation runner/)).toBeInTheDocument();
  });

  it("shows a newly registered method without any frontend change", () => {
    const added: MethodDef = { method_id: "keyword_overlap", name: "Keyword overlap", description: "New!", implemented: true, class_name: "KeywordOverlapRetriever", file: "retrieval/dense_retrieval/keyword_overlap.py", parameters: {} };
    const stage = { ...dense, methods: [...dense.methods, added] };
    render(<TooltipProvider><StageConfigCard stage={stage} config={configFor([stage])} system={system} /></TooltipProvider>);
    const option = screen.getByRole("option", { name: "Keyword overlap" }) as HTMLOptionElement;
    expect(option.disabled).toBe(false);
  });

  it("darkens and disables blocks without an implemented method (e.g. Metadata Prefiltering)", () => {
    render(<DisabledStage stage={prefilter} />);
    const block = screen.getByTestId("disabled-stage-metadata_prefiltering");
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
    render(<TooltipProvider><ExecutionTab stages={[prefilter, dense, reranking]} chat={chat} /></TooltipProvider>);
    expect(screen.getByText("Candidate Retrieval")).toBeInTheDocument(); // group label from the registry
    expect(screen.getByTestId("disabled-stage-metadata_prefiltering")).toHaveTextContent("Not implemented");
    const card = screen.getByTestId("stage-dense_retrieval");
    expect(card).toHaveTextContent("Qdrant cosine");
    fireEvent.click(card.querySelector("summary")!);
    expect(screen.getByText("similarity 0.8123")).toBeInTheDocument();
    expect(screen.getByTestId("disabled-stage-reranking")).toBeInTheDocument();
    expect(screen.queryByTestId("stage-reranking")).toBeNull();
  });

  it("shows a block's extra details (e.g. an LLM rewrite check) when it reported them", () => {
    const rewrite = record({ details: { raw_output: "credit limit", validation: "fallback" } });
    const chat = { messages: [], selected: "r1", select: vi.fn(),
      traces: { r1: { requestId: "r1", question: "How?", status: "completed", stages: { dense_retrieval: rewrite } } } } as unknown as ChatState;  // prettier-ignore
    render(<TooltipProvider><ExecutionTab stages={[dense]} chat={chat} /></TooltipProvider>);
    fireEvent.click(screen.getByTestId("stage-dense_retrieval").querySelector("summary")!);
    expect(screen.getByRole("tab", { name: "Details" })).toBeInTheDocument();
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

describe("AAES in the chat", () => {
  it("sends earlier user turns as history and shows the action badge", async () => {
    const { historyOf } = await import("@/hooks/useChat");
    const { ActionBadge } = await import("@/components/chat/MessageItem");
    expect(historyOf([{ id: "1", role: "user", content: "I'm at ERICA." }, { id: "2", role: "assistant", content: "ok" },
      { id: "3", role: "user", content: "I'm a master's student." }])).toEqual(["I'm at ERICA.", "I'm a master's student."]);
    render(<ActionBadge action="CONDITIONAL" />);
    expect(screen.getByTestId("action-badge")).toHaveTextContent("Conditional answer");
  });
});
