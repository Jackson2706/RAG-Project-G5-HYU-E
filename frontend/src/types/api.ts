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
}

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

export interface OllamaModel {
  name: string;
  parameter_size: string | null;
  capabilities: string[];
}
