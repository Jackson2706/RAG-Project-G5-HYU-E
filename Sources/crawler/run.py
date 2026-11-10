"""Command-line crawl orchestration and immutable snapshot building."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

import httpx

from app.config import DATA_DIR

from .dedup import deduplicate
from .extract import (
    AttachmentInput,
    canonical_uri,
    attachment_extension,
    discover_attachments,
    discover_board_posts,
    discover_erica_menu,
    discover_sitemap,
    extract_document,
)
from .fetch import CrawlStore, FetchEvent, Fetcher, RedirectNotAllowed, RequestLimitReached, USER_AGENT, read_manifest
from .sites import ERICA_BOARD_NAMES, SITES, SiteConfig, get_site, is_board_listing


FIXTURE_DIR = Path(__file__).resolve().parent / "tests" / "fixtures"


def _empty_site_report() -> dict[str, object]:
    return {
        "requests": 0,
        "by_status": {},
        "by_kind": {},
        "skipped_robots": 0,
        "skipped_deny": 0,
        "skipped_no_english": 0,
        "documents": 0,
        "attachments_by_type": {},
    }


def _selected_sites(name: str) -> list[SiteConfig]:
    if name == "all":
        return [site for site in SITES.values() if site.enabled]
    return [get_site(name)]


def _fixture_bytes(filename: str) -> bytes:
    return (FIXTURE_DIR / filename).read_bytes()


def dry_run_plan(
    site_names: list[SiteConfig],
    from_fixtures: bool = False,
    data_dir: Path = DATA_DIR,
) -> dict[str, list[str]]:
    plan = {site.name: list(site.seeds) for site in site_names}
    if "seoul" in plan:
        raw = _fixture_bytes("seoul_sitemap.xml") if from_fixtures else None
        if raw:
            plan["seoul"].extend(discover_sitemap(raw))
    if "erica" in plan:
        if from_fixtures:
            plan["erica"].extend(discover_erica_menu(_fixture_bytes("erica_eng_index.html")))
            plan["erica"].extend(discover_board_posts(
                _fixture_bytes("erica_board_s4_1_eng_list.html"),
                "https://global.hanyang.ac.kr/bbs/board.php?bo_table=s4_1_eng",
            ))
    manifest = read_manifest(Path(data_dir) / "HYU" / "manifest.jsonl")
    for record in manifest:
        raw_path = record.get("raw_path")
        if record.get("status") != 200 or not raw_path or record.get("site") not in plan:
            continue
        raw = (Path(data_dir) / str(raw_path)).read_bytes()
        if record.get("kind") == "sitemap" and record.get("site") == "seoul":
            plan["seoul"].extend(discover_sitemap(raw))
        elif canonical_uri(str(record.get("url"))) == "https://global.hanyang.ac.kr/eng/":
            plan["erica"].extend(discover_erica_menu(raw))
    for name, urls in plan.items():
        config = get_site(name)
        deduped: list[str] = []
        seen = set()
        for url in urls:
            uri = canonical_uri(url)
            if config.is_allowed(url) and uri not in seen:
                deduped.append(url)
                seen.add(uri)
        plan[name] = deduped
    return plan


def print_dry_run(site_names: list[SiteConfig], from_fixtures: bool = False, data_dir: Path = DATA_DIR) -> None:
    plan = dry_run_plan(site_names, from_fixtures, data_dir)
    for site in site_names:
        print(f"[{site.name}] allow: {', '.join(site.allow_patterns)}")
        print(f"[{site.name}] deny: {', '.join(site.deny_patterns)}; other hosts")
        for url in plan[site.name]:
            print(f"[{site.name}] {url}")
        print(f"[{site.name}] count: {len(plan[site.name])}")


class Crawler:
    def __init__(
        self,
        data_dir: Path = DATA_DIR,
        client: httpx.Client | None = None,
        fetcher: Fetcher | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.store = CrawlStore(self.data_dir)
        self._owns_client = client is None and fetcher is None
        self.client = client or httpx.Client(timeout=30.0)
        self.fetcher = fetcher or Fetcher(self.client)
        self.report: dict[str, object] = {
            "sites": {},
            "lang_coverage_histogram": {str(index): 0 for index in range(10)},
            "warnings": {},
            "wall_time": 0.0,
            "user_agent": self.fetcher.user_agent,
            "min_interval": self.fetcher.min_interval,
        }
        self._site_records: list[dict[str, object]] = []
        self._completed_records: dict[str, dict[str, object]] = {}
        self._completed_urls: dict[str, dict[str, object]] = {}

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _record_events(
        self,
        events: list[FetchEvent],
        config: SiteConfig,
        kind: str,
        parent_uri: str | None,
        filename: str | None,
    ) -> list[dict[str, object]]:
        records = []
        for event in events:
            event_kind = event.kind or kind
            record = self.store.record_event(
                event,
                site=config.name,
                kind=event_kind,
                parent_uri=None if event_kind == "robots" else parent_uri,
                filename_override=filename if event_kind == "attachment" else None,
            )
            records.append(record)
            self._site_records.append(record)
        return records

    def _fetch(
        self,
        url: str,
        config: SiteConfig,
        kind: str,
        *,
        parent_uri: str | None = None,
        filename: str | None = None,
    ) -> tuple[httpx.Response | None, dict[str, object] | None]:
        response = None
        try:
            response = self.fetcher.get(url, allowed_hosts=config.allowed_hosts, kind=kind)
        except (httpx.HTTPError, RedirectNotAllowed):
            pass  # the manifest records status "error"; one bad URL must not stop a long crawl
        finally:
            records = self._record_events(
                self.fetcher.drain_events(), config, kind, parent_uri, filename
            )
        logical = next((record for record in reversed(records) if record["kind"] == kind), None)
        return response, logical

    def _is_completed(self, url: str, completed: set[str], resume: bool) -> bool:
        return resume and canonical_uri(url) in completed

    def _raw_for_record(self, record: dict[str, object]) -> bytes:
        return (self.data_dir / str(record["raw_path"])).read_bytes()

    def _attachment_inputs(self, records: list[dict[str, object]]) -> list[AttachmentInput]:
        inputs = []
        for record in records:
            raw_path = record.get("raw_path")
            if record.get("status") != 200 or not raw_path:
                continue
            path = self.data_dir / str(raw_path)
            inputs.append(AttachmentInput(
                data=path.read_bytes(),
                filename=str(record.get("filename") or path.name),
                content_type=str(record.get("content_type") or ""),
                canonical_uri=str(record["canonical_uri"]),
                sha256=str(record.get("sha256") or ""),
            ))
        return inputs

    def _extract_preview(
        self,
        page_record: dict[str, object],
        attachments: list[dict[str, object]],
    ) -> dict[str, object] | None:
        raw_path = page_record.get("raw_path")
        if page_record.get("status") != 200 or not raw_path:
            return None
        document = extract_document(
            (self.data_dir / str(raw_path)).read_bytes(),
            str(page_record["url"]),
            str(page_record["site"]),
            self._attachment_inputs(attachments),
            str(page_record.get("sha256") or ""),
        )
        if document:
            path = self.data_dir / "HYU" / "extracted" / f"{document['doc_id']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return document

    def _fetch_page(self, url: str, config: SiteConfig, completed: set[str], resume: bool) -> None:
        site_report = self.report["sites"][config.name]
        if self._is_completed(url, completed, resume):
            page_record = self._completed_records[canonical_uri(url)]
            page_raw = self._raw_for_record(page_record)
        else:
            response, page_record = self._fetch(url, config, "page")
            if not response or response.status_code != 200 or not page_record:
                return
            page_raw = response.content
        discovered = discover_attachments(page_raw, url, config)
        attachment_records = []
        for item in discovered:
            if self._is_completed(item["url"], completed, resume):
                attachment_records.append(self._completed_records[canonical_uri(item["url"])])
                continue
            try:
                _, record = self._fetch(
                    item["url"], config, "attachment",
                    parent_uri=canonical_uri(url), filename=item["filename"],
                )
            except RequestLimitReached:
                break
            if record:
                attachment_records.append(record)
                extension = attachment_extension(item["filename"]) or "unknown"
                counts = site_report["attachments_by_type"]
                counts[extension] = counts.get(extension, 0) + 1
        document = self._extract_preview(page_record, attachment_records)
        if document:
            site_report["documents"] += 1
            ratio = float(document["lang_coverage"]["ratio"])
            bucket = str(min(9, int(ratio * 10)))
            self.report["lang_coverage_histogram"][bucket] += 1
            warning_counts = Counter(str(warning).split(":", 1)[0] for warning in document["warnings"])
            self.report["warnings"] = dict(Counter(self.report["warnings"]) + warning_counts)
        else:
            site_report["skipped_no_english"] += 1

    def _crawl_seoul(self, config: SiteConfig, completed: set[str], resume: bool) -> None:
        sitemap_url = config.seeds[0]
        if self._is_completed(sitemap_url, completed, resume):
            sitemap_raw = self._raw_for_record(self._completed_records[canonical_uri(sitemap_url)])
        else:
            response, _ = self._fetch(sitemap_url, config, "sitemap")
            if not response or response.status_code != 200:
                return
            sitemap_raw = response.content
        all_urls = [
            node.text or ""
            for node in ET.fromstring(sitemap_raw).iter()
            if node.tag.endswith("}loc") or node.tag == "loc"
        ]
        self.report["sites"][config.name]["skipped_deny"] += sum(
            bool(url.strip()) and not config.is_allowed(url.strip()) for url in all_urls
        )
        for url in discover_sitemap(sitemap_raw, config):
            try:
                self._fetch_page(url, config, completed, resume)
            except RequestLimitReached:
                return

    @staticmethod
    def _listing_page(url: str, page: int) -> str:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        query["page"] = [str(page)]
        pairs = [(key, value) for key in query for value in query[key]]
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(pairs), ""))

    def _crawl_board(self, listing_url: str, config: SiteConfig, completed: set[str], resume: bool) -> None:
        known_posts: set[str] = set()
        page = 1
        while True:
            url = self._listing_page(listing_url, page)
            if resume and url in self._completed_urls:
                listing_raw = self._raw_for_record(self._completed_urls[url])
            else:
                response, _ = self._fetch(url, config, "listing")
                if not response or response.status_code != 200:
                    return
                listing_raw = response.content
            posts = discover_board_posts(listing_raw, url)
            new_posts = [post for post in posts if post not in known_posts]
            if not new_posts:
                return
            known_posts.update(new_posts)
            for post in new_posts:
                self._fetch_page(post, config, completed, resume)
            page += 1

    def _crawl_erica(self, config: SiteConfig, completed: set[str], resume: bool) -> None:
        if self._is_completed(config.seeds[0], completed, resume):
            index_raw = self._raw_for_record(self._completed_records[canonical_uri(config.seeds[0])])
        else:
            response, _ = self._fetch(config.seeds[0], config, "page")
            index_raw = response.content if response and response.status_code == 200 else b""
        urls = discover_erica_menu(index_raw) if index_raw else []
        urls.extend(config.seeds[1:])
        seen = set()
        for url in urls:
            uri = canonical_uri(url)
            if uri in seen:
                continue
            seen.add(uri)
            if is_board_listing(url):
                self._crawl_board(url, config, completed, resume)
            else:
                self._fetch_page(url, config, completed, resume)

    def crawl(self, sites: list[SiteConfig], *, resume: bool = False, max_pages: int | None = None) -> dict[str, object]:
        start = time.monotonic()
        existing = read_manifest(self.store.manifest_path)
        if existing and not resume:
            raise RuntimeError("manifest is not empty; use --resume to continue")
        completed = {
            str(record["canonical_uri"])
            for record in existing
            if record.get("status") == 200
        }
        self._completed_records = {
            str(record["canonical_uri"]): record
            for record in existing
            if record.get("status") == 200 and record.get("raw_path")
        }
        self._completed_urls = {
            str(record["url"]): record
            for record in existing
            if record.get("status") == 200 and record.get("raw_path")
        }
        for config in sites:
            site_start = self.fetcher.request_count
            self._site_records = []
            self.report["sites"][config.name] = _empty_site_report()
            self.fetcher.max_requests = site_start + max_pages if max_pages is not None else None
            try:
                if config.name == "seoul":
                    self._crawl_seoul(config, completed, resume)
                elif config.name == "erica":
                    self._crawl_erica(config, completed, resume)
            except RequestLimitReached:
                pass
            site_report = self.report["sites"][config.name]
            site_report["requests"] = self.fetcher.request_count - site_start
            site_report["by_status"] = dict(Counter(str(record["status"]) for record in self._site_records))
            site_report["by_kind"] = dict(Counter(str(record["kind"]) for record in self._site_records))
            site_report["skipped_robots"] = sum(record["status"] == "skipped_robots" for record in self._site_records)
        self.report["wall_time"] = time.monotonic() - start
        report_path = self.data_dir / "HYU" / "crawl_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(self.report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return self.report


def _successful_manifest_records(records: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    successful = {}
    for record in records:
        if record.get("status") == 200 and record.get("raw_path"):
            successful[str(record["canonical_uri"])] = record
    return successful


def _snapshot_documents(data_dir: Path, records: list[dict[str, object]]) -> list[dict[str, object]]:
    successful = _successful_manifest_records(records)
    attachments: dict[str, list[dict[str, object]]] = {}
    for record in successful.values():
        if record.get("kind") == "attachment" and record.get("parent_uri"):
            attachments.setdefault(str(record["parent_uri"]), []).append(record)
    documents = []
    for record in successful.values():
        if record.get("kind") != "page":
            continue
        raw = (data_dir / str(record["raw_path"])).read_bytes()
        inputs = []
        for item in attachments.get(str(record["canonical_uri"]), []):
            path = data_dir / str(item["raw_path"])
            inputs.append(AttachmentInput(
                data=path.read_bytes(),
                filename=str(item.get("filename") or path.name),
                content_type=str(item.get("content_type") or ""),
                canonical_uri=str(item["canonical_uri"]),
                sha256=str(item.get("sha256") or ""),
            ))
        document = extract_document(
            raw,
            str(record["url"]),
            str(record["site"]),
            inputs,
            str(record.get("sha256") or ""),
        )
        if document:
            documents.append(document)
    return deduplicate(documents)


def build_snapshot(data_dir: Path = DATA_DIR, today: datetime | None = None) -> Path:
    data_dir = Path(data_dir)
    manifest_path = data_dir / "HYU" / "manifest.jsonl"
    if not manifest_path.exists() or not manifest_path.read_bytes():
        raise RuntimeError("manifest is empty; there is nothing to snapshot")
    manifest_bytes = manifest_path.read_bytes()
    date = (today or datetime.now(timezone.utc)).strftime("%Y%m%d")
    snapshot_id = f"hyu-{date}-{hashlib.sha256(manifest_bytes).hexdigest()[:8]}"
    snapshot_dir = data_dir / "HYU" / "snapshots" / snapshot_id
    if snapshot_dir.exists():
        raise FileExistsError(f"snapshot already exists: {snapshot_id}")

    records = read_manifest(manifest_path)
    documents = _snapshot_documents(data_dir, records)
    aliases = sum(len(document["aliases"]) for document in documents)
    family_ids = {document["version_family_id"] for document in documents if document["version_family_id"]}
    base_report_path = data_dir / "HYU" / "crawl_report.json"
    base_report = json.loads(base_report_path.read_text(encoding="utf-8")) if base_report_path.exists() else {}
    report = {
        **base_report,
        "snapshot": {
            "id": snapshot_id,
            "documents": len(documents),
            "aliases": aliases,
            "families": len(family_ids),
            "superseded": sum(bool(document["superseded_by"]) for document in documents),
        },
    }

    snapshot_dir.mkdir(parents=True)
    documents_path = snapshot_dir / "documents.jsonl"
    report_path = snapshot_dir / "crawl_report.json"
    documents_path.write_text(
        "".join(json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n" for document in documents),
        encoding="utf-8",
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_lines = []
    for path in (documents_path, report_path):
        checksum_lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n")
    (snapshot_dir / "SNAPSHOT.sha256").write_text("".join(checksum_lines), encoding="utf-8")
    return snapshot_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl approved HYU English pages")
    parser.add_argument("--site", choices=(*SITES, "all"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--from-fixtures", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--build-snapshot", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, data_dir: Path = DATA_DIR, client: httpx.Client | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.site == "studyerica":
        print("studyerica is disabled until Gate G2", file=sys.stderr)
        return 2
    if args.max_pages is not None and args.max_pages < 1:
        print("--max-pages must be at least 1", file=sys.stderr)
        return 2
    if args.build_snapshot:
        try:
            path = build_snapshot(data_dir)
        except (RuntimeError, FileExistsError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(path)
        return 0
    sites = _selected_sites(args.site)
    if args.dry_run:
        print_dry_run(sites, args.from_fixtures, data_dir)
        return 0
    crawler = Crawler(data_dir, client=client)
    try:
        crawler.crawl(sites, resume=args.resume, max_pages=args.max_pages)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        crawler.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

