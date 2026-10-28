# Sample corpus (synthetic)

These five files are **invented** for development and testing. They are *not* official
Hanyang University policy. Each file says so in its first paragraph.

They cover every supported format and the metadata cases the pipeline must handle:

| File | Format | Declared metadata | Purpose |
|---|---|---|---|
| `orientation_guide.md` | Markdown + YAML front matter | campus SEOUL, freshman/international | headings, table, list |
| `course_registration.md` | Markdown + front matter | campus ALL (university-wide) | numbered steps, table |
| `scholarships.html` | HTML + `<meta>` tags | campus ALL, undergraduate/international | HTML lists/tables |
| `student_services.txt` | Plain text | none (all unknown) | unknown-metadata handling |
| `erica_housing.md` | Markdown + front matter | campus ERICA | campus filtering |

Ingest them with `python scripts/ingest.py --path data/samples`.
This README is skipped by the loader. Put real, approved documents in `data/raw/`.
