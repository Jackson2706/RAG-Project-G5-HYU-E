# Raw documents

Put the real, approved English documents here: **PDF, TXT, Markdown (`.md`) or HTML**.
Sub-folders are fine. Ingestion only reads these files and never changes them.

Then run, from the `hyu-compass/` folder:

```bash
conda activate RAG
python scripts/ingest.py --path data/raw
```

Tips:
- Only save documents you are allowed to access and share. Do not bypass logins or download
  limits on https://book.hanyang.ac.kr/html/.
- Markdown files may start with front matter like `title: My Title` between `---` lines; the
  title is used in citations. Other files use their `<title>`, PDF title or first line.
- This README itself is skipped by ingestion.
