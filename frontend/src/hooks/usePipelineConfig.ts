import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { applyPreset, completeDraft } from "@/lib/config";
import { storage } from "@/lib/utils";
import { api } from "@/services/api";
import type { PipelineConfig, Preset, Registry, ValidationResult } from "@/types/api";

const DRAFT_KEY = "hyu-compass:draft-config";

/** Registry + configuration draft + backend validation (debounced) + presets. */
export function usePipelineConfig() {
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [serverDefaults, setServerDefaults] = useState<PipelineConfig | null>(null);
  const [activeIndexConfig, setActiveIndexConfig] = useState<PipelineConfig["stages"] | null>(null);
  const [draft, setDraftState] = useState<PipelineConfig | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [validating, setValidating] = useState(false);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const seq = useRef(0);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [reg, cfg, pre] = await Promise.all([api.registry(), api.config(), api.presets()]);
      const defaults = completeDraft(reg, cfg.config);
      setRegistry(reg);
      setServerDefaults(defaults);
      setActiveIndexConfig(cfg.active_index_config);
      setPresets(pre);
      const saved = storage.get<PipelineConfig | null>(DRAFT_KEY, null);
      setDraftState(saved ? completeDraft(reg, saved) : defaults);
    } catch (err) {
      setLoadError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const setDraft = useCallback((next: PipelineConfig) => {
    setDraftState(next);
    storage.set(DRAFT_KEY, next);
  }, []);

  // Validate every draft change against the backend registry (single source of truth).
  useEffect(() => {
    if (!draft) return;
    const id = ++seq.current;
    setValidating(true);
    const timer = setTimeout(async () => {
      try {
        const result = await api.validate(draft);
        if (id === seq.current) setValidation(result);
      } catch (err) {
        if (id === seq.current)
          setValidation({ valid: false, errors: [{ stage_id: null, param: null, message: (err as Error).message }], warnings: [], resolved: null });
      } finally {
        if (id === seq.current) setValidating(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [draft]);

  const resetAll = useCallback(() => serverDefaults && setDraft(serverDefaults), [serverDefaults, setDraft]);

  const loadPreset = useCallback(
    (preset: Preset) => registry && serverDefaults && setDraft(applyPreset(registry, serverDefaults, preset.config)),
    [registry, serverDefaults, setDraft],
  );

  const savePreset = useCallback(
    async (name: string, description: string) => {
      if (!draft) return;
      await api.savePreset(name, description, draft);
      setPresets(await api.presets());
    },
    [draft],
  );

  const importConfig = useCallback(
    (raw: unknown) => {
      if (!registry) return;
      const obj = raw as { stages?: PipelineConfig["stages"]; config?: PipelineConfig };
      const stages = obj.config?.stages ?? obj.stages;
      if (!stages || typeof stages !== "object") throw new Error("JSON must contain a 'stages' object");
      setDraft(completeDraft(registry, { stages }));
    },
    [registry, setDraft],
  );

  return useMemo(
    () => ({ registry, draft, setDraft, validation, validating, presets, loadError, reload: load, resetAll, loadPreset, savePreset,
             importConfig, activeIndexConfig, serverDefaults }),  // prettier-ignore
    [registry, draft, setDraft, validation, validating, presets, loadError, load, resetAll, loadPreset, savePreset, importConfig, activeIndexConfig, serverDefaults],
  );
}

export type PipelineConfigState = ReturnType<typeof usePipelineConfig>;
