# Raw source documents

Place manually collected, **approved** English documents here (PDF, TXT, Markdown, HTML).
Sub-folders are scanned recursively. Files are never modified by ingestion.

Do not bypass authentication or download restrictions of https://book.hanyang.ac.kr/html/ —
save only documents you are allowed to access and share with the team.

Optional metadata: Markdown files may start with YAML front matter and HTML files may use
`<meta name="..." content="...">` tags. Recognized keys: `title`, `document_type`, `campus`
(SEOUL | ERICA | ALL), `audience` (undergraduate, graduate, international, exchange, freshman, all),
`academic_year`, `issuer`, `publication_date`, `effective_from`, `effective_until`, `topics`.
Values outside the vocabularies are dropped with a warning; missing values stay unknown.

Uploads made through the API are stored in `raw/uploads/`. This README is skipped by the loader.
