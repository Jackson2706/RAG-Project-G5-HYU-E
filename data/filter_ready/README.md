# Canonical ingestion corpus

This directory contains 713 cleaned Markdown documents: 662 PDF-derived units and 51 official web additions. Ingest only this directory for real Hanyang data. Original PDFs and web snapshots remain in `data/raw/`. No intermediate Markdown or converted folder is needed to ingest or validate it.

```bash
conda run -n RAG python scripts/validate_filter_data.py --report data/filter_ready.validation.json
conda run -n RAG python scripts/ingest.py --path data/filter_ready
```

Ingestion replaces the current index. Metadata manifests, schema, filter vocabulary and validation reports live beside this directory as `data/filter_ready*.json`. The base manifest registers the web extension. Validation checks raw and prepared hashes, parser compatibility, scope metadata, filtering examples and chunk sizes. Historical parent source IDs and intermediate hashes remain as provenance; they are not live file paths. Exact original section coverage was verified before removing the intermediate copies.

Metadata includes campus, academic level/audience, document type, topic, department/college where supported, and year/term only when explicitly stated. Missing values mean unknown. `ALL` means explicitly shared scope. Collection dates are not effective dates. The majors guidebook has conflicting cover/filename years, so neither is treated as its academic year. Spring 2027 admission tuition tables quote Fall 2026 reference amounts. Current backend controls support only their implemented fields; preparing metadata does not add new filter controls.

Web additions cover selected checked English material, not every archived source or every scanned PDF page. Older or undated immigration/insurance rules and expired notices remain raw-only. Some official sites blocked collection. Original sources are in `data/raw/web_2026-11-12/`; source URL, SHA-256, collection date and supported scope are included in prepared records.

For future web preparation, use `scripts/collect_hanyang_web.py` and `scripts/prepare_hanyang_web.py`. Curated undergraduate summaries are retained in `scripts/data/hanyang_2027_undergraduate.json`. Preparation extracts HTML in memory and only selected topics enter filter_ready. Selection rules and summaries target the dated snapshot and need review for a new admission cycle. The old base-conversion helper was retired because its intermediate inputs were removed; additional raw PDFs require a new reviewed extraction pass.

Draft evaluation banks now reference prepared unit paths. Review relevance and answerability labels against the expanded corpus before reporting benchmark scores. No measured accuracy improvement is claimed.
