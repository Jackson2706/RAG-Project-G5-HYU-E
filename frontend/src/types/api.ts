// TypeScript mirrors of the backend Pydantic models (backend/app/models/*).
// The registry itself is fetched at runtime — no algorithm list is hardcoded here.

export type ImplementationStatus = "implemented" | "planned" | "unavailable";
export type StageStatus = "pending" | "running" | "completed" | "bypassed" | "failed";
export type ParamType = "integer" | "float" | "boolean" | "enum" | "string" | "string_list" | "multi_enum";
export type Control =
  | "slider" | "number" | "toggle" | "select" | "text" | "textarea" | "tags" | "multiselect" | "ollama_model";
export type Scope = "runtime" | "ingestion" | "index";
export type ParamValue = string | number | boolean | null | string[];

export interface Option {
  value: string | number | boolean;
  label: string;
}

export interface ParameterSpec {
  name: string;
  label: string;
  type: ParamType;
  default: ParamValue;
  description: string;
  control: Control;
  scope: Scope;
  level: "basic" | "advanced";
  nullable: boolean;
  min: number | null;
  max: number | null;
  step: number | null;
  unit: string | null;
  options: Option[] | null;
  visible_when: Record<string, ParamValue[]> | null;
}

export interface MethodSpec {
  method_id: string;
  display_name: string;
  description: string;
  status: ImplementationStatus;
  implementation: string | null;
  parameters: ParameterSpec[];
  constraints: string[];
}

export interface StageSpec {
  stage_id: string;
  stage_name: string;
  description: string;
  category: "offline" | "online";
  can_disable: boolean;
  enabled: boolean;
  selected_method: string;
  available_methods: MethodSpec[];
  reads: string[];
  writes: string[];
  dependencies: string[];
  requires_reindexing: boolean;
  implementation_status: ImplementationStatus;
  input_schema?: Record<string, string>;
  output_schema?: Record<string, string>;
}

export interface Registry {
  stages: StageSpec[];
  online_order: string[];
  offline_order: string[];
}

export interface StageConfig {
  enabled?: boolean | null;
  method?: string | null;
  params: Record<string, ParamValue>;
}

export interface PipelineConfig {
  stages: Record<string, StageConfig>;
}

export interface ResolvedConfig {
  stages: Record<string, { enabled: boolean; method: string; params: Record<string, ParamValue> }>;
  config_hash: string;
}

export interface ValidationIssue {
  stage_id: string | null;
  param: string | null;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  resolved: ResolvedConfig | null;
}

export interface Preset {
  preset_id: string;
  name: string;
  description: string;
  builtin: boolean;
  config: PipelineConfig;
  available: boolean;
  unavailable_reason: string | null;
}

export interface SourceSpan {
  start: number;
  end: number;
}

export interface Citation {
  marker: string;
  chunk_id: string;
  doc_id: string;
  title: string | null;
  source_uri: string | null;
  section_path: string[];
  page_number: number | null;
  source_span: SourceSpan | null;
  excerpt: string;
  cited: boolean;
  resolved: boolean;
  span_verified: boolean | null;
}

export interface CitationReport {
  method: string;
  cited_markers: string[];
  invalid_markers: string[];
  uncited_evidence: string[];
  unresolved: string[];
  span_failures: string[];
  sentences_total: number;
  sentences_with_citation: number;
  note: string;
}

export type Outcome = "answered" | "insufficient_evidence" | "abstained" | "failed";

export interface AnswerResult {
  answer: string;
  outcome: Outcome;
  citations: Citation[];
  citation_report: CitationReport | null;
  guard_notes: string[];
  model: string | null;
}

export interface StageTrace {
  request_id: string;
  stage_id: string;
  stage_name: string;
  method_id: string | null;
  status: StageStatus;
  implementation_status: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  summary: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  configuration: Record<string, unknown>;
  error: string | null;
  bypass_reason: string | null;
}

export interface ExecutionTrace {
  request_id: string;
  session_id: string | null;
  created_at: string;
  question: string;
  status: "running" | "completed" | "failed" | "cancelled";
  config: ResolvedConfig;
  index_revision: Record<string, unknown>;
  stages: StageTrace[];
  result: AnswerResult | null;
  total_ms: number | null;
  error: string | null;
}

export type EventType =
  | "pipeline_started" | "stage_started" | "stage_completed" | "stage_bypassed" | "stage_failed"
  | "answer_delta" | "answer_completed" | "pipeline_completed" | "pipeline_error";

export interface PipelineEvent {
  type: EventType;
  request_id: string;
  timestamp: string;
  stage?: StageTrace;
  delta?: string;
  result?: AnswerResult;
  trace?: ExecutionTrace;
  error?: string;
  data?: Record<string, unknown>;
}

export interface OllamaModel {
  name: string;
  size: number | null;
  family: string | null;
  parameter_size: string | null;
  quantization: string | null;
}

export interface OllamaStatus {
  base_url: string;
  reachable?: boolean;
  version?: string;
  model_count?: number;
  configured_model: string | null;
  error?: string;
  hint?: string;
}

export interface Health {
  status: "ok" | "degraded";
  mongodb: { ok: boolean; error?: string };
  qdrant: { ok: boolean; error?: string; mode?: string };
  ollama: { ok: boolean; error?: string; version?: string };
  active_index: {
    revision_id: string;
    collection: string;
    doc_count: number;
    chunk_count: number;
    embedding_model: string;
    dimension: number;
  } | null;
}

export interface DocumentSummary {
  doc_id: string;
  source_uri: string;
  title: string | null;
  media_type: string;
  campus: string | null;
  audience: string[];
  document_type: string | null;
  academic_year: string | null;
  topics: string[];
  version_id: string;
  parse_warnings: string[];
  metadata_provenance: Record<string, string>;
}
