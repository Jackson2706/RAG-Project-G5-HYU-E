import { useCallback, useEffect, useState } from "react";

import { storage } from "@/lib/utils";
import { api } from "@/services/api";
import type { ConfigError, MethodDef, ParamValue, StageChoices, StageDef } from "@/types/api";

const KEY = "hyu-compass:pipeline-config";

/** The group label to show above stage `i`, if it starts a new group (e.g. "Candidate Retrieval"). */
export function groupStartsAt(stages: StageDef[], i: number): string | null {
  const group = stages[i].group;
  return group && stages[i - 1]?.group !== group ? group : null;
}

export function methodOf(stage: StageDef, methodId: string | null): MethodDef | undefined {
  return stage.methods.find((m) => m.method_id === methodId);
}

function defaultsOf(method: MethodDef | undefined): Record<string, ParamValue> {
  return Object.fromEntries(Object.entries(method?.parameters ?? {}).map(([name, p]) => [name, p.default]));
}

/** The registry's default choice for every stage. */
export function defaultChoices(stages: StageDef[]): StageChoices {
  return Object.fromEntries(stages.map((s) => [s.stage_id, { method: s.default_method, params: defaultsOf(methodOf(s, s.default_method)) }]));
}

/** Keep saved choices only if they still fit the current registry (methods may have changed). */
function restore(stages: StageDef[], saved: StageChoices): StageChoices {
  const choices = defaultChoices(stages);
  for (const s of stages) {
    const old = saved[s.stage_id];
    const method = old && (old.method === null ? s.optional : methodOf(s, old.method)?.implemented) ? old.method : undefined;
    if (method === undefined) continue;
    const defaults = defaultsOf(methodOf(s, method));
    choices[s.stage_id] = { method, params: Object.fromEntries(Object.keys(defaults).map((k) => [k, old.params[k] ?? defaults[k]])) };
  }
  return choices;
}

/**
 * The method registry and the user's choices. All rules live in the backend:
 * every change is sent to POST /api/pipeline/config/validate.
 */
export function usePipelineConfig() {
  const [stages, setStages] = useState<StageDef[]>([]);
  const [choices, setChoices] = useState<StageChoices | null>(null);
  const [errors, setErrors] = useState<ConfigError[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    api
      .registry()
      .then(({ stages }) => {
        setStages(stages);
        setChoices(restore(stages, storage.get<StageChoices>(KEY, {})));
      })
      .catch((err: Error) => setLoadError(err.message));
  }, []);

  useEffect(() => {
    if (!choices) return;
    storage.set(KEY, choices);
    const timer = setTimeout(() => {
      api.validate(choices).then((r) => setErrors(r.errors)).catch((err: Error) => setErrors([{ stage_id: null, param: null, message: err.message }]));
    }, 250);
    return () => clearTimeout(timer);
  }, [choices]);

  const setMethod = useCallback((stage: StageDef, methodId: string | null) => {
    setChoices((c) => c && { ...c, [stage.stage_id]: { method: methodId, params: defaultsOf(methodOf(stage, methodId)) } });
  }, []);

  const setParam = useCallback((stageId: string, name: string, value: ParamValue) => {
    setChoices((c) => c && { ...c, [stageId]: { ...c[stageId], params: { ...c[stageId].params, [name]: value } } });
  }, []);

  const resetStage = useCallback((stage: StageDef) => setMethod(stage, stage.default_method), [setMethod]);
  const resetAll = useCallback(() => setChoices(defaultChoices(stages)), [stages]);

  return { stages, choices, errors, valid: errors.length === 0, setMethod, setParam, resetStage, resetAll, loadError };
}

export type PipelineConfigState = ReturnType<typeof usePipelineConfig>;
