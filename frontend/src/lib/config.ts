// Pure helpers for editing a configuration draft. All rules (ranges, availability, cross-stage
// constraints) are enforced by the backend validator; these helpers only shape the draft.
import type { MethodSpec, ParameterSpec, ParamValue, PipelineConfig, Registry, StageSpec, ValidationResult } from "@/types/api";

export function stageById(registry: Registry): Record<string, StageSpec> {
  return Object.fromEntries(registry.stages.map((s) => [s.stage_id, s]));
}

export function methodOf(spec: StageSpec, methodId: string | null | undefined): MethodSpec | undefined {
  return spec.available_methods.find((m) => m.method_id === (methodId ?? spec.selected_method));
}

export function methodDefaults(method: MethodSpec): Record<string, ParamValue> {
  return Object.fromEntries(method.parameters.map((p) => [p.name, p.default]));
}

/** Fill every stage with enabled/method/params so the UI always has concrete values to show. */
export function completeDraft(registry: Registry, draft: PipelineConfig): PipelineConfig {
  const stages: PipelineConfig["stages"] = {};
  for (const spec of registry.stages) {
    const current = draft.stages[spec.stage_id];
    const method = methodOf(spec, current?.method) ?? methodOf(spec, spec.selected_method)!;
    stages[spec.stage_id] = {
      enabled: current?.enabled ?? spec.enabled,
      method: method.method_id,
      params: { ...methodDefaults(method), ...pick(current?.params ?? {}, method) },
    };
  }
  return { stages };
}

function pick(params: Record<string, ParamValue>, method: MethodSpec): Record<string, ParamValue> {
  const names = new Set(method.parameters.map((p) => p.name));
  return Object.fromEntries(Object.entries(params).filter(([k]) => names.has(k)));
}

export function setParam(draft: PipelineConfig, stageId: string, name: string, value: ParamValue): PipelineConfig {
  const stage = draft.stages[stageId];
  return { stages: { ...draft.stages, [stageId]: { ...stage, params: { ...stage.params, [name]: value } } } };
}

export function setEnabled(draft: PipelineConfig, stageId: string, enabled: boolean): PipelineConfig {
  return { stages: { ...draft.stages, [stageId]: { ...draft.stages[stageId], enabled } } };
}

/** Switch method: new method's defaults, keeping values of parameters that share a name. */
export function setMethod(draft: PipelineConfig, spec: StageSpec, methodId: string): PipelineConfig {
  const method = methodOf(spec, methodId)!;
  const previous = draft.stages[spec.stage_id]?.params ?? {};
  const params = { ...methodDefaults(method), ...pick(previous, method) };
  return { stages: { ...draft.stages, [spec.stage_id]: { ...draft.stages[spec.stage_id], method: methodId, params } } };
}

export function resetStage(draft: PipelineConfig, spec: StageSpec): PipelineConfig {
  const method = methodOf(spec, spec.selected_method)!;
  return { stages: { ...draft.stages, [spec.stage_id]: { enabled: spec.enabled, method: method.method_id, params: methodDefaults(method) } } };
}

export function isVisible(param: ParameterSpec, params: Record<string, ParamValue>): boolean {
  if (!param.visible_when) return true;
  return Object.entries(param.visible_when).every(([k, allowed]) => allowed.includes(params[k]));
}

/** Only the online stages are sent with a chat request. */
export function onlineConfig(registry: Registry, draft: PipelineConfig): PipelineConfig {
  return { stages: Object.fromEntries(registry.online_order.filter((id) => draft.stages[id]).map((id) => [id, draft.stages[id]])) };
}

export function offlineConfig(registry: Registry, draft: PipelineConfig): PipelineConfig {
  return { stages: Object.fromEntries(registry.offline_order.filter((id) => draft.stages[id]).map((id) => [id, draft.stages[id]])) };
}

export function issuesFor(validation: ValidationResult | null, stageId: string, param?: string) {
  const match = (i: { stage_id: string | null; param: string | null }) => i.stage_id === stageId && (param === undefined || i.param === param);
  return {
    errors: validation?.errors.filter(match) ?? [],
    warnings: validation?.warnings.filter(match) ?? [],
  };
}

/** Merge a (partial) preset on top of the registry defaults. */
export function applyPreset(registry: Registry, base: PipelineConfig, preset: PipelineConfig): PipelineConfig {
  const defaults = completeDraft(registry, { stages: Object.fromEntries(registry.offline_order.map((id) => [id, base.stages[id]])) });
  return completeDraft(registry, { stages: { ...defaults.stages, ...preset.stages } });
}
