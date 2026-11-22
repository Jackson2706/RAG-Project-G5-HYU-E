import { useCallback, useEffect, useState } from "react";

import { storage } from "@/lib/utils";
import { api } from "@/services/api";
import type { ConfigError, IndexRevision, MethodDef, ParamValue, Preset, StageChoices, StageDef } from "@/types/api";

const KEY = "hyu-compass:pipeline-config";
const META_KEY = "hyu-compass:pipeline-meta"; // the chosen preset and index
const CUSTOM_KEY = "hyu-compass:custom-config"; // "Save custom configuration"
export const CUSTOM = "__custom__";

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
  const [presets, setPresets] = useState<Preset[]>([]);
  const [indexes, setIndexes] = useState<IndexRevision[]>([]);
  const [meta, setMeta] = useState(() => storage.get<{ presetId: string | null; indexId: string }>(META_KEY, { presetId: null, indexId: "default" }));

  useEffect(() => {
    api
      .registry()
      .then(({ stages }) => {
        setStages(stages);
        setChoices(restore(stages, storage.get<StageChoices>(KEY, {})));
      })
      .catch((err: Error) => setLoadError(err.message));
    api.presets().then((r) => setPresets(r.presets)).catch(() => setPresets([]));
    api.indexes().then((r) => setIndexes(r.indexes)).catch(() => setIndexes([]));
  }, []);

  useEffect(() => storage.set(META_KEY, meta), [meta]);

  useEffect(() => {
    if (!choices) return;
    storage.set(KEY, choices);
    const timer = setTimeout(() => {
      api.validate(choices).then((r) => setErrors(r.errors)).catch((err: Error) => setErrors([{ stage_id: null, param: null, message: err.message }]));
    }, 250);
    return () => clearTimeout(timer);
  }, [choices]);

  // A manual change keeps the preset name visible but marks the configuration as modified.
  const [modified, setModified] = useState(false);

  const setMethod = useCallback((stage: StageDef, methodId: string | null) => {
    setChoices((c) => c && { ...c, [stage.stage_id]: { method: methodId, params: defaultsOf(methodOf(stage, methodId)) } });
    setModified(true);
  }, []);

  const setParam = useCallback((stageId: string, name: string, value: ParamValue) => {
    setChoices((c) => c && { ...c, [stageId]: { ...c[stageId], params: { ...c[stageId].params, [name]: value } } });
    setModified(true);
  }, []);

  const resetStage = useCallback((stage: StageDef) => setMethod(stage, stage.default_method), [setMethod]);
  const resetAll = useCallback(() => {
    setChoices(defaultChoices(stages));
    setMeta((m) => ({ ...m, presetId: null }));
    setModified(false);
  }, [stages]);

  /** Load a preset's validated configuration into every stage (offline stages too: they show what re-indexing would build). */
  const applyPreset = useCallback((presetId: string | null) => {
    const config = presetId === CUSTOM ? storage.get<StageChoices | null>(CUSTOM_KEY, null) : presets.find((p) => p.id === presetId)?.config;
    if (presetId && config) setChoices(restore(stages, config));
    setMeta((m) => ({ ...m, presetId }));
    setModified(false);
  }, [presets, stages]);

  const saveCustom = useCallback(() => {
    if (choices) storage.set(CUSTOM_KEY, choices);
    setMeta((m) => ({ ...m, presetId: CUSTOM }));
    setModified(false);
  }, [choices]);
  const hasCustom = storage.get<StageChoices | null>(CUSTOM_KEY, null) !== null;

  /** Search another index revision. Its offline settings are copied in, so the query embedding matches its vectors. */
  const selectIndex = useCallback((indexId: string) => {
    const built = indexes.find((i) => i.index_id === indexId)?.manifest?.config;
    if (built) setChoices((c) => c && restore(stages, { ...c, ...built }));
    setMeta((m) => ({ ...m, indexId }));
  }, [indexes, stages]);

  const exportJson = useCallback(() => JSON.stringify({ preset: meta.presetId, index_id: meta.indexId, stages: choices }, null, 2), [choices, meta]);
  const importJson = useCallback((text: string) => {
    const data = JSON.parse(text) as { stages?: StageChoices; index_id?: string };
    if (!data.stages) throw new Error("The file has no \"stages\" object.");
    setChoices(restore(stages, data.stages));
    setMeta((m) => ({ presetId: null, indexId: data.index_id ?? m.indexId }));
    setModified(true);
  }, [stages]);

  return {
    stages, choices, errors, valid: errors.length === 0, setMethod, setParam, resetStage, resetAll, loadError,
    presets, presetId: meta.presetId, modified, applyPreset, saveCustom, hasCustom, exportJson, importJson,
    indexes, indexId: meta.indexId, selectIndex,
  };
}

export type PipelineConfigState = ReturnType<typeof usePipelineConfig>;
