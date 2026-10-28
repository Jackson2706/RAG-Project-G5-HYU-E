import { useCallback, useEffect, useState } from "react";

import { api } from "@/services/api";
import type { Health, OllamaModel, OllamaStatus } from "@/types/api";

/** Backend health + Ollama status and installed models. */
export function useSystem() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [ollama, setOllama] = useState<OllamaStatus | null>(null);
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [defaultModel, setDefaultModel] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.health());
      setHealthError(null);
    } catch (err) {
      setHealth(null);
      setHealthError((err as Error).message);
    }
  }, []);

  const refreshModels = useCallback(async () => {
    setLoadingModels(true);
    try {
      const status = await api.ollamaStatus();
      setOllama(status);
      if (status.reachable) {
        const res = await api.ollamaModels();
        setModels(res.models);
        setDefaultModel(res.default);
      } else {
        setModels([]);
      }
    } catch (err) {
      setOllama({ base_url: "", configured_model: null, reachable: false, error: (err as Error).message });
    } finally {
      setLoadingModels(false);
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
    void refreshModels();
    const id = setInterval(refreshHealth, 30000);
    return () => clearInterval(id);
  }, [refreshHealth, refreshModels]);

  return { health, healthError, refreshHealth, ollama, models, defaultModel, loadingModels, refreshModels };
}

export type SystemState = ReturnType<typeof useSystem>;
