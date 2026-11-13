// TypeScript versions of the data the backend sends (see backend/app/*.py).

export type ParamValue = number | string | boolean;

/** One hyperparameter of a method (registry.py → Param). */
export interface ParamDef {
  type: "integer" | "float" | "boolean" | "enum" | "string";
  default: ParamValue;
  label: string;
  description: string;
  ui: "slider" | "number" | "toggle" | "select" | "text" | "ollama_model";
  min: number | null;
  max: number | null;
  step: number | null;
  options: string[] | null;
  scope: "runtime" | "ingestion" | "index";
  advanced: boolean; // shown under "Advanced settings"
}

/** One algorithm for a block (registry.py → Method). */
export interface MethodDef {
  method_id: string;
  name: string;
  description: string;
  implemented: boolean;
  class_name: string;
  file: string; // e.g. "retrieval/dense_retrieval/qdrant_cosine.py"
  parameters: Record<string, ParamDef>;
}

/** One pipeline block, from GET /api/pipeline/registry (registry.py → Stage). */
export interface StageDef {
  stage_id: string;
  name: string;
  phase: "offline" | "online";
  description: string;
  base_class: string;
  folder: string; // e.g. "app/rag/blocks/retrieval/dense_retrieval/"
  group: string | null; // e.g. "Candidate Retrieval"
  optional: boolean;
  default_method: string | null;
  implemented: boolean; // true if at least one method is implemented
  methods: MethodDef[];
}

/** The chosen method and parameters for every stage: {stage_id: {method, params}}. */
export type StageChoices = Record<string, { method: string | null; params: Record<string, ParamValue> }>;

export interface ConfigError {
  stage_id: string | null;
  param: string | null;
  message: string;
}

/** What one stage did during one request (app/tracing.py → Tracer). */
export interface StageRecord {
  stage_id: string;
  name: string;
  method_id: string | null;
  method_name: string | null;
  status: "running" | "completed" | "failed" | "skipped";
  input: unknown;
  output: unknown;
  params: Record<string, unknown>;
  summary: string;
  duration_ms: number | null;
  error: string | null;
  details?: unknown; // extra facts a block reported (e.g. an LLM's raw output and how it was checked)
}

/** A source shown under the answer (source attribution, not claim verification). */
export interface SourceReference {
  label: string;
  cited: boolean;
  chunk_id: string;
  doc_id: string;
  title: string;
  source_uri: string;
  section: string | null;
  page_number: number | null;
  score: number;
  excerpt: string;
}

/** The full record of one question (also stored in MongoDB → GET /api/traces/{id}). */
export interface Trace {
  request_id: string;
  question: string;
  created_at: string;
  config: StageChoices; // the exact methods and parameters this request used
  status: "running" | "completed" | "failed" | "cancelled";
  stages: StageRecord[];
  answer: string;
  outcome: "answered" | "insufficient_context" | "error" | null;
  sources: SourceReference[];
  model: string | null;
  error: string | null;
  total_ms?: number;
  action?: AaesAction | null; // AAES presets only
  unknown_condition_evidence?: boolean | null;
}

export type AaesAction = "ANSWER" | "CONDITIONAL" | "CLARIFY" | "ABSTAIN" | "CONFIRM";

/** Events of POST /api/chat/stream. */
export type StreamEvent =
  | { type: "started"; request_id: string; config: StageChoices }
  | { type: "stage"; request_id: string; stage: StageRecord }
  | { type: "answer_delta"; request_id: string; text: string }
  | { type: "done"; request_id: string; trace: Trace };

export interface IndexInfo {
  documents: number;
  chunks: number;
  vectors: number;
  chunking: { method: string; chunk_size: number; chunk_overlap: number } | null; // how the index was built
  embedding_method: string | null;
}

export interface Health {
  mongodb: { ok: boolean; error?: string };
  qdrant: { ok: boolean; error?: string };
  ollama: { ok: boolean; error?: string; models?: number };
  index: IndexInfo | null;
}

/** A named experiment configuration (backend/app/rag/presets.py), validated by the registry. */
export interface Preset {
  id: string; // e.g. "R2_HYBRID_RRF"
  kind: "baseline" | "offline" | "online" | "proposed";
  name: string;
  description: string;
  enabled: boolean;
  config: StageChoices | null; // complete validated configuration (null if disabled or invalid)
  errors: ConfigError[];
  needs_demo_case?: boolean; // oracle presets (G1, A2) run only with a labeled demo case
}

/** A labeled dev case for the demo (GET /api/demo/cases); never a test case. */
export interface DemoCase {
  case_id: string;
  slice: string;
  question: string;
  history: string[]; // earlier user turns, sent as the session history
  stated_profile: Record<string, string>;
  expected_behavior: string;
  story?: string | null;
}

/** One index revision (GET /api/indexes): the app's index or a benchmark index. */
export interface IndexRevision {
  index_id: string; // "default" = the app's own index
  manifest: {
    built_at?: string;
    corpus?: { dataset?: string; source?: unknown; smoke_slice?: boolean };
    config?: StageChoices; // the offline stages it was built with
    embedding_contract?: { method?: string; model?: string; dimension?: number };
    vector_index?: { hnsw_built?: boolean };
  } | null;
  info: IndexInfo;
}

export interface OllamaModel {
  name: string;
  parameter_size: string | null;
  capabilities: string[];
}
