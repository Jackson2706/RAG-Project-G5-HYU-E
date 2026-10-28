// Frontend tests. registry.fixture.json is exported from the real backend registry
// (`python -c "from app.rag.registry import registry_payload; ..."`, see docs/DEVELOPER_GUIDE.md).
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StageConfigCard } from "@/components/pipeline/StageConfigCard";
import { StageTraceCard } from "@/components/pipeline/StageTraceCard";
import { Workspace } from "@/components/layout/Workspace";
import { TooltipProvider } from "@/components/ui/primitives";
import { applyEvent, type LiveTrace } from "@/hooks/useChat";
import type { SystemState } from "@/hooks/useSystem";
import { completeDraft, isVisible, onlineConfig, setMethod, setParam, stageById } from "@/lib/config";
import { parseSseChunk } from "@/services/api";
import type { PipelineConfig, Registry, StageTrace, ValidationResult } from "@/types/api";
import registryJson from "./registry.fixture.json";

const registry = registryJson as unknown as Registry;
const stages = stageById(registry);
const system = { models: [], defaultModel: null, ollama: null, loadingModels: false, refreshModels: vi.fn() } as unknown as SystemState;

function stageTrace(over: Partial<StageTrace>): StageTrace {
  return { request_id: "r1", stage_id: "reranking", stage_name: "Reranking", method_id: "cross_encoder", status: "bypassed",
           implementation_status: "planned", started_at: null, completed_at: null, duration_ms: 0, summary: "Disabled", input: {},
           output: {}, configuration: {}, error: null, bypass_reason: "Reranking is disabled in this configuration; input passed through unchanged.", ...over };  // prettier-ignore
}

describe("SSE parsing", () => {
  it("parses complete events and keeps the partial remainder", () => {
    const a = `event: stage_started\ndata: {"type":"stage_started","request_id":"r1","timestamp":"t"}\n\n`;
    const b = `event: answer_delta\ndata: {"type":"answer_delta","request_id":"r1","timestamp":"t","delta":"Hi"}\n\n`;
    const { events, rest } = parseSseChunk(a + b + ": keep-alive\n\n" + "event: answer_del");
    expect(events.map((e) => e.type)).toEqual(["stage_started", "answer_delta"]);
    expect(events[1].delta).toBe("Hi");
    expect(rest).toBe("event: answer_del");
  });
});

describe("live trace reducer", () => {
  it("records stage events per request and replaces them with the final trace", () => {
    let t: LiveTrace = { request_id: "r1", question: "q", status: "running", stages: {} };
    t = applyEvent(t, { type: "stage_started", request_id: "r1", timestamp: "", stage: stageTrace({ stage_id: "dense_retrieval", status: "running" }) });
    expect(t.stages.dense_retrieval.status).toBe("running");
    t = applyEvent(t, { type: "stage_completed", request_id: "r1", timestamp: "", stage: stageTrace({ stage_id: "dense_retrieval", status: "completed" }) });
    expect(t.stages.dense_retrieval.status).toBe("completed");
    const final = { request_id: "r1", status: "failed", stages: [stageTrace({ stage_id: "generation", status: "failed" })] } as never;
    t = applyEvent(t, { type: "pipeline_error", request_id: "r1", timestamp: "", trace: final });
    expect(t.status).toBe("failed");
    expect(Object.keys(t.stages)).toEqual(["generation"]);
  });
});

describe("configuration helpers", () => {
  const draft = completeDraft(registry, { stages: {} });

  it("fills every registered stage with registry defaults", () => {
    expect(Object.keys(draft.stages).sort()).toEqual(registry.stages.map((s) => s.stage_id).sort());
    expect(draft.stages.dense_retrieval.params.top_k).toBe(10);
  });

  it("switching method keeps parameters that share a name", () => {
    const edited = setParam(draft, "evidence_selection", "max_chunks", 7);
    const switched = setMethod(edited, stages.evidence_selection, "token_budget");
    expect(switched.stages.evidence_selection.params.max_chunks).toBe(7);
    expect(switched.stages.evidence_selection.params.max_tokens).toBe(1200);
  });

  it("evaluates visibility conditions and sends only online stages", () => {
    const hnsw = stages.dense_retrieval.available_methods[0].parameters.find((p) => p.name === "hnsw_ef")!;
    expect(isVisible(hnsw, { exact: false })).toBe(true);
    expect(isVisible(hnsw, { exact: true })).toBe(false);
    const online = onlineConfig(registry, draft);
    expect(Object.keys(online.stages)).toEqual(registry.online_order);
    expect(online.stages.chunking).toBeUndefined();
  });
});

function renderCard(stageId: string, draft: PipelineConfig, validation: ValidationResult | null = null, onChange = vi.fn()) {
  render(
    <TooltipProvider>
      <StageConfigCard spec={stages[stageId]} draft={draft} onChange={onChange} validation={validation} advanced system={system} index={1} />
    </TooltipProvider>,
  );
  return onChange;
}

describe("registry-driven configuration UI", () => {
  const draft = completeDraft(registry, { stages: {} });

  it("renders controls from the registry and shows planned methods as disabled", () => {
    renderCard("reranking", setParam(draft, "reranking", "top_n", 20));
    const select = screen.getByLabelText("Method") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.textContent)).toEqual([
      "Cross-encoder — planned", "LLM reranker — planned", "Rule-aware reranker — planned",
    ]);
    expect(screen.getAllByText("planned").length).toBeGreaterThan(0);
  });

  it("disables planned options once the stage is enabled", () => {
    const enabled = { stages: { ...draft.stages, metadata_filtering: { ...draft.stages.metadata_filtering, enabled: true } } };
    renderCard("metadata_filtering", enabled);
    const options = Array.from((screen.getByLabelText("Method") as HTMLSelectElement).options);
    expect(options.find((o) => o.value === "exact")!.disabled).toBe(false);
    expect(options.find((o) => o.value === "boolean")!.disabled).toBe(true);
  });

  it("shows backend validation errors next to the parameter and edits through onChange", () => {
    const validation: ValidationResult = { valid: false, warnings: [], resolved: null,
      errors: [{ stage_id: "dense_retrieval", param: "top_k", message: "Top K must be ≤ 100" }] };  // prettier-ignore
    const onChange = renderCard("dense_retrieval", draft, validation);
    expect(screen.getByRole("alert")).toHaveTextContent("Top K must be ≤ 100");
    fireEvent.change(screen.getAllByLabelText("Top K").find((el) => el.tagName === "INPUT")!, { target: { value: "25" } });
    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls.at(-1)![0].stages.dense_retrieval.params.top_k).toBe(25);
  });
});

describe("execution trace UI", () => {
  it("shows bypass reason and actual output candidates", () => {
    render(
      <TooltipProvider>
        <StageTraceCard spec={stages.reranking} index={9} lookup={{}} trace={stageTrace({})} />
        <StageTraceCard spec={stages.dense_retrieval} index={5} methodName="Qdrant vector search" lookup={{ c1: { chunk_id: "c1", title: "Guide", text: "Joined text" } }}
          trace={stageTrace({ stage_id: "dense_retrieval", status: "completed", summary: "1 candidates", duration_ms: 12.5, bypass_reason: null,
                              output: { candidates: [{ chunk_id: "c1", doc_id: "d1", dense_score: 0.81234 }] } })} />
      </TooltipProvider>,
    );
    expect(screen.getByTestId("stage-trace-reranking")).toHaveAttribute("data-status", "bypassed");
    fireEvent.click(screen.getByTestId("stage-trace-reranking").querySelector("summary")!);
    expect(screen.getByText(/input passed through unchanged/)).toBeInTheDocument();
    expect(screen.getByText("13 ms")).toBeInTheDocument();
    const dense = screen.getByTestId("stage-trace-dense_retrieval");
    fireEvent.click(dense.querySelector("summary")!);
    fireEvent.mouseDown(screen.getAllByRole("tab", { name: "Output" })[1]);
    expect(screen.getByText("dense 0.8123")).toBeInTheDocument();
    expect(screen.getByText("Joined text")).toBeInTheDocument();
  });
});

describe("resizable layout", () => {
  it("renders a keyboard-focusable separator between the two panels", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() });
    render(<Workspace mobileView="chat" pipeline={<div>pipeline-panel</div>} chat={<div>chat-panel</div>} />);
    const sep = screen.getByRole("separator");
    expect(sep).toHaveAttribute("tabindex", "0");
    expect(screen.getByText("pipeline-panel")).toBeInTheDocument();
    expect(screen.getByText("chat-panel")).toBeInTheDocument();
  });

  it("shows one panel at a time on narrow screens", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() });
    render(<Workspace mobileView="pipeline" pipeline={<div>pipeline-panel</div>} chat={<div>chat-panel</div>} />);
    expect(screen.getByText("pipeline-panel")).toBeInTheDocument();
    expect(screen.queryByText("chat-panel")).toBeNull();
  });
});
