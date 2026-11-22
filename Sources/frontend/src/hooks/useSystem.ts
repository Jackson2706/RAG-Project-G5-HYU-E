import { useCallback, useEffect, useState } from "react";

import { api } from "@/services/api";
import type { Health, OllamaModel } from "@/types/api";

/** Backend status and installed Ollama models. */
export function useSystem() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [defaultModel, setDefaultModel] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setHealth(await api.health());
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
    api.models().then((r) => { setModels(r.models); setDefaultModel(r.default); }).catch(() => setModels([]));
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { health, error, models, defaultModel, refresh };
}

export type SystemState = ReturnType<typeof useSystem>;
