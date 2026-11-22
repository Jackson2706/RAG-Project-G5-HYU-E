# HYU crawler

Run the crawler from `Sources/` in the `RAG` Conda environment. It accepts only the approved
Seoul OIA and ERICA OIA English hosts. `studyerica` stays disabled until Gate G2.

Inspect the plan without making a request:

```bash
python -m crawler.run --site all --dry-run
```

Start or resume the real crawl:

```bash
caffeinate -i python -m crawler.run --site all --resume
```

Use `--site seoul` or `--site erica` to limit the run. `--max-pages N` caps HTTP requests per
site, including robots.txt and sitemap requests. A non-empty manifest requires `--resume`.

After reviewing `Sources/data/HYU/crawl_report.json` and the previews under `Sources/data/HYU/extracted/`, build
the frozen snapshot offline:

```bash
python -m crawler.run --build-snapshot
```

The crawler stores content-addressed raw bytes under `Sources/data/HYU/raw/` and appends request records
to `Sources/data/HYU/manifest.jsonl`. Snapshot output is written to
`Sources/data/HYU/snapshots/hyu-YYYYMMDD-<manifest-hash>/`. An existing snapshot directory is never
overwritten.

Run the offline tests with:

```bash
python -m pytest -q crawler/tests
```
