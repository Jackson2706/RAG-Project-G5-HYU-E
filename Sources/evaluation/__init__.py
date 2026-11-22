"""HYU Compass headless evaluation: BEIR benchmarks and RAG evaluation without the UI or FastAPI.

Run from the Sources/ folder with the Conda environment `RAG`:

    python -m evaluation.runner --suite all --dry-run
    python -m evaluation.runner --suite all
    python -m evaluation.reports --run-id main

Every RAG algorithm comes from backend/app (the same registry, pipeline and blocks the app uses);
this package only adds datasets, metrics, the experiment runner and reports.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))  # so `import app` works, like scripts/ingest.py
