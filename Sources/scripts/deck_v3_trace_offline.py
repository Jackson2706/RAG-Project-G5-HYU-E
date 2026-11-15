"""Deck v3 Part 2b: one real page through the offline pipeline -> Report/slides/deck_v3/trace_offline.md.

Run from Sources/:  python scripts/deck_v3_trace_offline.py
Page: ERICA "International Student Insurance" (https://global.hanyang.ac.kr/eng/s3/s3_2_1.php). Reads the raw HTML
(manifest), the frozen snapshot record, and the r5 chunks with their tags from MongoDB (read-only). Nothing is rebuilt.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import get_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.rag.schemas import make_doc_id  # noqa: E402

URL = "https://global.hanyang.ac.kr/eng/s3/s3_2_1.php"
OUT = ROOT.parent / "Report" / "slides" / "deck_v3" / "trace_offline.md"
TAG_CHUNKS = ("University Group Insurance Premium", "Penalties for Overdue Payment")


def main() -> int:
    manifest = next(r for r in map(json.loads, open(ROOT / "data" / "HYU" / "manifest.jsonl")) if r["url"] == URL)
    raw = (ROOT / "data" / manifest["raw_path"]).read_text(encoding="utf-8", errors="replace")
    i = raw.find("University Group Insurance Premium")
    snippet = raw[max(0, i - 300):i + 500]
    doc = next(d for d in map(json.loads, open(ROOT / "data" / "HYU" / "snapshots" / "hyu-20261110-97dc1269" / "documents.jsonl")) if d["source_uri"] == URL)
    settings = get_settings()
    db = Database.connect(settings).for_index("hyu_20261110_97dc1269_r5")
    chunks = sorted(db.chunks.find({"doc_id": make_doc_id(URL)}, {"_id": 0, "embedding": 0}), key=lambda c: int(c.get("chunk_index", 0)))
    lines = ["# Offline trace: one page through crawl → clean → chunk → tag → index", "",
             f"Page: {URL} (ERICA, \"{doc['title']}\"). Raw file `Sources/data/{manifest['raw_path']}` (gitignored), fetched "
             f"{manifest['fetched_at']}, {manifest['bytes']:,} bytes, sha256 `{manifest['sha256'][:16]}…`.", "",
             "## 1. Raw HTML (snippet around the premium table)", "", "```html", snippet.strip(), "```", "",
             "## 2. Cleaned text in the snapshot (`documents.jsonl`, e-mails masked)", "",
             f"{len(doc['text']):,} characters, {len(doc.get('spans') or [])} spans (headings, paragraphs, table rows). First 900 characters:", "",
             "```", doc["text"][:900], "```", "",
             f"## 3. Chunks in index r5 ({len(chunks)} chunks; section-aware, 320 BGE tokens, 48 overlap)", "",
             "| # | Section heading | Tokens | Characters | First words |", "|---|---|---|---|---|"]  # fmt: skip
    for c in chunks:
        lines.append(f"| {c.get('chunk_index')} | {(c.get('section') or '')[:50]} | {c.get('token_count')} | {len(c.get('text') or '')} | {(c.get('text') or '')[:70].replace(chr(10), ' ').replace('|', '/')} |")
    lines += ["", "## 4. Tags on two chunks (applicability condition, rules only in r5)", ""]
    for key in TAG_CHUNKS:
        c = next((c for c in chunks if key in (c.get("section") or "") + (c.get("text") or "")), None)
        if not c:
            lines += [f"Chunk with \"{key}\": not found.", ""]
            continue
        app = c.get("applicability") or {}
        lines += [f"**Chunk {c.get('chunk_index')}** (contains \"{key}\"), condition status `{c.get('condition_status')}`, tag bucket `{app.get('tag_bucket') or c.get('tag_bucket')}`:", "",
                  "```", (c.get("text") or "")[:500], "```", "", "```json",
                  json.dumps({k: app.get(k) for k in ("campus", "scope", "constraints", "any_of", "requirements", "effective_term", "superseded_by", "extraction_method")}, indent=1, ensure_ascii=False),
                  "```", ""]  # fmt: skip
    text = "\n".join(lines) + "\n"
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email]", html.unescape(text) if False else text)  # mask any address in the raw snippet
    OUT.write_text(text, encoding="utf-8")
    print("wrote", OUT, len(chunks), "chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
