# Project data

- `raw/`: original PDFs and official web archives; retain for provenance and future cleaning.
- `filter_ready/`: canonical cleaned Markdown with filter metadata. This is the production ingestion target.
- `eval/`: draft evaluation questions and metadata cases.
- `samples/`: synthetic fixtures used by tests and demos; not official university policy.
- `filter_ready*.json`: manifests, schemas, vocabularies and validation reports; these are used by validation and are not ingestion documents.

```bash
conda run -n RAG python scripts/validate_filter_data.py --report data/filter_ready.validation.json
conda run -n RAG python scripts/ingest.py --path data/filter_ready
```

Ingestion replaces the current index. Do not combine raw sources or samples with the production corpus. Disposable converted files and intermediate Markdown have been removed. Historical parent IDs in the base manifest identify removed preparation inputs, not live paths. The 713 prepared documents and original raw sources remain available.
