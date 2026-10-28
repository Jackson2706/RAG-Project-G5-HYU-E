# Sample documents (invented)

These five files are **made up** for practice and tests. They are **not** official Hanyang
University policy, and each file says so at the top.

| File | Format |
|---|---|
| `orientation_guide.md` | Markdown with front matter, headings, a table and a list |
| `course_registration.md` | Markdown with numbered steps and a table |
| `scholarships.html` | HTML with lists and a table |
| `student_services.txt` | plain text |
| `erica_housing.md` | Markdown |

Ingest them from the `hyu-compass/` folder with `python scripts/ingest.py --path data/samples`.
The backend tests use copies of these files. `../eval/sample_questions.jsonl` has 14 practice
questions about them, with the document that answers each one. It is useful when you tune a new
method (see `docs/05_ADD_NEW_METHOD.md`). This README is skipped by ingestion.
