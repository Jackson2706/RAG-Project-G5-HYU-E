"""What every pipeline block has in common.

Each block folder (ingestion/chunking/, retrieval/dense_retrieval/, …) has a `base.py` with an abstract class such as
`BaseDenseRetriever`. Those classes inherit from `PipelineBlock`, so every algorithm automatically has:

    self.params     its hyperparameters, already validated by app/rag/registry.py
    self.services   shared tools: self.services.db, .embedder, .ollama, .settings
    self.method_id  its ID in the registry (set by the registry when it creates the block)
"""

from __future__ import annotations

from abc import ABC
from typing import Any

from app.rag.schemas import Services


class PipelineBlock(ABC):
    def __init__(self, params: dict[str, Any], services: Services) -> None:
        self.params = params
        self.services = services
        self.method_id = ""
