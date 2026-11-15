"""Check every page quote of the deck v2 brief against the frozen snapshot text AND the raw crawled bytes.

Run from Sources/:  python scripts/verify_deck_quotes.py   # -> Report/slides/deck_v2/quotes.csv (quote, url, found_in_snapshot, found_in_raw, raw_source)
                    python scripts/verify_deck_quotes.py quotes.json out.csv   # another list: [[id, url, quote, kind], ...]

Whitespace is collapsed and HTML entities decoded before matching; a quote counts as verbatim only if it is a
substring of the page text after that normalisation. Raw sources: the page's HTML (tags stripped) and, for notices
whose text comes from an attachment, the attachment files (PDF text via pypdf). Table rows are checked cell by cell,
because the snapshot writes a table row as "header: value; ..." while the page shows a table.
"""

from __future__ import annotations

import csv
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SNAP = DATA / "HYU" / "snapshots" / "hyu-20261110-97dc1269" / "documents.jsonl"
OUT = ROOT.parent / "Report" / "slides" / "deck_v2" / "quotes.csv"

# (id, url, quote, kind) kind "text" = verbatim sentence; "table" = cells joined by " | ", each checked on its own.
QUOTES = [
    ("hours_seoul", "https://oia.hanyang.ac.kr/notice/1813514",
     "The number of allowed hours for part-time work (For those submitting the Korean language proficiency standard) is 20 hours per week for language training students, 20 hours per week for undergraduate students (25 hours for IEQAS-certified universities), and 30 hours per week for masters/doctoral degree students.", "text"),
    ("hours_seoul_no_topik", "https://oia.hanyang.ac.kr/notice/1813514",
     "In case the Korean language proficiency standard is not fulfilled, the number of allowed work hours is limited to 10 hours for language training/undergraduate students, and 15 hours for masters/doctoral degree students", "text"),
    ("topik_standard_seoul", "https://oia.hanyang.ac.kr/notice/1813514",
     "Korean language proficiency standard (TOPIK): Language training level 2, Associate degree level 3, Bachelor's degree (1st-2nd year) level 3, Bachelor's degree (3rd-4th year) level 4, Masters/doctoral degree level 4 or higher", "text"),
    ("hours_erica_bachelor", "https://global.hanyang.ac.kr/eng/s3/s3_1.php",
     "Bachelor's | Year 1-2 | Level 3 | O | No Restrictions | 30 hours | No Restrictions", "table"),
    ("hours_erica_bachelor_no_topik", "https://global.hanyang.ac.kr/eng/s3/s3_1.php",
     "Bachelor's | Year 1-2 | Level 3 | X | No Restrictions | 10 hours | 10 hours", "table"),
    ("hours_erica_graduate", "https://global.hanyang.ac.kr/eng/s3/s3_1.php",
     "Master's/Doctoral | N/A | Level 4 | O | No Restrictions | 35 hours | No Restrictions", "table"),
    ("insurance_seoul_enrolled", "https://oia.hanyang.ac.kr/notice/1814901",
     "Enrolled students : Premiums are paid in full through Hanyang University’s budget (Students do not need to pay premiums themselves)", "text"),
    ("insurance_seoul_completed", "https://oia.hanyang.ac.kr/notice/1814901",
     "Students who completed coursework : Students who wish to enroll in insurance, they must pay directly the premiun of 25,000 won themselves.", "text"),
    ("insurance_erica_premium", "https://global.hanyang.ac.kr/eng/s3/s3_2_1.php",
     "University Group Insurance Premium KRW 25,000 (same premium for undergraduate and graduate schools)", "text"),
    ("insurance_erica_tuition", "https://global.hanyang.ac.kr/eng/s3/s3_2_1.php",
     "Students must pay their insurance premium (lump-sum) when paying for their tuition", "text"),
    ("insurance_erica_returning", "https://global.hanyang.ac.kr/eng/s3/s3_2_1.php",
     "Returning students who took a leave of absence after paying tuition or those who completed the course residing in Korea must subscribe to the insurance individually through the insurance company's website", "text"),
    ("nhi_2026", "https://oia.hanyang.ac.kr/notice/1814881",
     "OIA would like to inform students of the contents of the National Health Insurance System for International Students that was applied from March 1, 2026. - Monthly Insurance premium: 76,390 won → 79,320 won", "text"),
    ("nhi_2025", "https://oia.hanyang.ac.kr/notice/1812000",
     "OIA would like to inform students of the contents of the National Health Insurance System for International Students that was applied from March 1, 2025. - Monthly Insurance premium: 75,490 won → 76,390 won", "text"),
    ("leave_erica", "https://global.hanyang.ac.kr/bbs/board.php?bo_table=s4_1_eng&wr_id=78",
     "Those who apply for the leave of absence must leave Korea within 30 days, regardless of their visa validity periods.", "text"),
    ("psych_test_seoul", "https://oia.hanyang.ac.kr/notice/1814943",
     "Eligibility: International undergraduate & graduate students at Seoul campus 🍀Period: Throughout March 🍀Language: Korean, English, Chinese 🍀Time required: About 1-2 minutes 🍀How to take the test: Log into HY-in > Foreign student > 유학생 정신건강 검사", "text"),
    ("psych_test_erica", "https://global.hanyang.ac.kr/eng/s3/s3_5_1.php",
     "Reservation Instructions Hanyang University Web Portal HY-in -> Application -> Personal Counseling/Psychological Testing", "text"),
    ("consequence_work_permit", "https://oia.hanyang.ac.kr/notice/1813514",
     "Both students and employers may be subject to punishment if working before obtaining a part-time work permit. (Employment activities are allowed only at a permitted workplace)", "text"),
    ("consequence_permit_violation", "https://global.hanyang.ac.kr/eng/s3/s3_1.php",
     "Applicants who have not received a part-time work permit or have a history of violating the conditions of the permit", "text"),
    ("consequence_insurance_erica", "https://global.hanyang.ac.kr/eng/s3/s3_2_1.php",
     "Failure to pay the insurance premium within the tuition payment period will render the student unable to enroll and thus be expelled from the university", "text"),
    ("consequence_nhi", "https://oia.hanyang.ac.kr/notice/1814881",
     "Failure to pay National Health Insurane will result in disadvantages in the immigration office's review of extension of stay period, so please pay by the deadline.", "text"),
    ("consequence_forgery", "https://oia.hanyang.ac.kr/notice/1808902",
     "This is an act of document forgery and whoever commits this crime shall be punished with fine or deportation from Korea.", "text"),
]  # fmt: skip


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def html_text(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    return norm(re.sub(r"<[^>]+>", " ", text))


def pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    return norm(" ".join(page.extract_text() or "" for page in PdfReader(str(path)).pages))


def main() -> int:
    quotes, out = (json.load(open(sys.argv[1])), Path(sys.argv[2])) if len(sys.argv) == 3 else (QUOTES, OUT)
    docs = {d["source_uri"]: d for d in map(json.loads, open(SNAP, encoding="utf-8"))}
    manifest = [json.loads(line) for line in open(DATA / "HYU" / "manifest.jsonl", encoding="utf-8")]
    raw_cache: dict[str, list[tuple[str, str]]] = {}

    def raw_texts(url: str) -> list[tuple[str, str]]:
        if url not in raw_cache:
            out = []
            for r in manifest:
                if r.get("raw_path") and (r["url"] == url or r.get("parent_uri") == url):
                    path = DATA / r["raw_path"]
                    if path.suffix == ".html":
                        out.append((r["raw_path"], html_text(path.read_bytes())))
                    elif path.read_bytes()[:5] == b"%PDF-":  # some attachments are stored with a broken suffix such as ".2m)"
                        out.append((r["raw_path"], pdf_text(path)))
            raw_cache[url] = out
        return raw_cache[url]

    rows, bad = [], 0
    for qid, url, quote, kind in quotes:
        snap = norm(docs[url]["text"]) if url in docs else ""
        parts = [p.strip() for p in quote.split("|")] if kind == "table" else [norm(quote)]
        in_snap = all(p in snap for p in parts)
        hit = next((src for src, text in raw_texts(url) if all(p in text for p in parts)), "")
        bad += not (in_snap and hit)
        rows.append({"id": qid, "url": url, "kind": kind, "found_in_snapshot": in_snap, "found_in_raw": bool(hit), "raw_source": hit, "quote": quote})
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        print(f"{r['id']:32} snapshot={r['found_in_snapshot']!s:5} raw={r['found_in_raw']!s:5} {r['raw_source']}")
    print("not fully verified:", bad)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
