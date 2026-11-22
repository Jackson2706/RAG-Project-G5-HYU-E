"""Rate-limited HTTP access, raw storage, and manifest writing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Callable, Iterable
from urllib.parse import unquote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.config import DATA_DIR

from .extract import canonical_uri, doc_id_for_url


USER_AGENT = (
    "HYU-Compass-CourseCrawler/0.1 "
    "(+https://github.com/Jackson2706/hyu-compass; student research project)"
)


class RequestLimitReached(RuntimeError):
    """Raised before a request would exceed the configured request budget."""


class RedirectNotAllowed(RuntimeError):
    """Raised when a redirect leaves the approved host set."""


@dataclass
class FetchEvent:
    url: str
    status: int | str
    response: httpx.Response | None = None
    error: str | None = None
    kind: str | None = None


class Fetcher:
    """A synchronous, injectable HTTP fetcher used by the CLI and unit tests."""

    def __init__(
        self,
        client: httpx.Client,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        min_interval: float = 2.5,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.client = client
        self.clock = clock
        self.sleep = sleep
        self.min_interval = min_interval
        self.user_agent = user_agent
        self.last_start: float | None = None
        self.request_count = 0
        self.max_requests: int | None = None
        self.events: list[FetchEvent] = []
        self._robots: dict[str, RobotFileParser] = {}

    def _wait_for_slot(self) -> None:
        if self.max_requests is not None and self.request_count >= self.max_requests:
            raise RequestLimitReached("request limit reached")
        if self.last_start is not None:
            remaining = self.min_interval - (self.clock() - self.last_start)
            if remaining > 0:
                self.sleep(remaining)
        self.last_start = self.clock()
        self.request_count += 1

    def _retry_after(self, value: str | None) -> float:
        if not value:
            return 1.0
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(value)
                now = datetime.now(timezone.utc)
                return max(0.0, (parsed - now).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return 1.0

    def _send(self, url: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            self._wait_for_slot()
            try:
                response = self.client.get(
                    url,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=False,
                )
            except httpx.RequestError as exc:
                last_error = exc
                if attempt == 2:
                    raise
                self.sleep(2**attempt)
                continue
            if response.status_code == 429 and attempt < 2:
                self.sleep(self._retry_after(response.headers.get("Retry-After")))
                continue
            if response.status_code >= 500 and attempt < 2:
                self.sleep(2**attempt)
                continue
            return response
        assert last_error is not None
        raise last_error

    def request(
        self,
        url: str,
        *,
        allowed_hosts: Iterable[str] | None = None,
        kind: str | None = None,
    ) -> httpx.Response:
        """Fetch a URL with retries and validate every redirect before following it."""
        allowed = {host.lower() for host in allowed_hosts or ()}
        original_url = url
        current = url
        try:
            original_host = (urlsplit(original_url).hostname or "").lower()
            if allowed and original_host not in allowed:
                raise RedirectNotAllowed(f"request to disallowed host: {original_host}")
            for _ in range(10):
                response = self._send(current)
                if not response.is_redirect:
                    self.events.append(FetchEvent(original_url, response.status_code, response, kind=kind))
                    return response
                location = response.headers.get("Location")
                if not location:
                    self.events.append(FetchEvent(original_url, response.status_code, response, kind=kind))
                    return response
                target = urljoin(str(response.url), location)
                target_host = (urlsplit(target).hostname or "").lower()
                if allowed and target_host not in allowed:
                    raise RedirectNotAllowed(f"redirect to disallowed host: {target_host}")
                current = target
            raise httpx.TooManyRedirects("more than 10 redirects", request=response.request)
        except RequestLimitReached:
            raise
        except Exception as exc:
            self.events.append(FetchEvent(original_url, "error", error=str(exc), kind=kind))
            raise

    def _load_robots(self, url: str, allowed_hosts: set[str]) -> RobotFileParser:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if host in self._robots:
            return self._robots[host]
        robots_url = f"{parsed.scheme or 'https'}://{host}/robots.txt"
        response = self.request(robots_url, allowed_hosts=allowed_hosts, kind="robots")
        parser = RobotFileParser(robots_url)
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
        elif response.status_code >= 500:
            parser.parse(["User-agent: *", "Disallow: /"])  # RFC 9309: server error means disallow all
        else:
            parser.parse([])
        self._robots[host] = parser
        return parser

    def get(
        self,
        url: str,
        *,
        allowed_hosts: Iterable[str],
        kind: str | None = None,
        check_robots: bool = True,
    ) -> httpx.Response | None:
        """Check robots once for the host, then fetch unless the path is disallowed."""
        allowed = {host.lower() for host in allowed_hosts}
        if check_robots:
            parser = self._load_robots(url, allowed)
            if not parser.can_fetch(self.user_agent, url):
                self.events.append(FetchEvent(url, "skipped_robots", kind=kind))
                return None
        return self.request(url, allowed_hosts=allowed, kind=kind)

    def fetch(
        self,
        url: str,
        *,
        allowed_hosts: Iterable[str] | None = None,
        kind: str | None = None,
        check_robots: bool = True,
    ) -> httpx.Response | None:
        """Fetch one URL; infer the starting host when no host set is supplied."""
        hosts = allowed_hosts or {(urlsplit(url).hostname or "").lower()}
        return self.get(url, allowed_hosts=hosts, kind=kind, check_robots=check_robots)

    def drain_events(self) -> list[FetchEvent]:
        events, self.events = self.events, []
        return events


CONTENT_EXTENSIONS = {
    "text/html": ".html",
    "application/xhtml+xml": ".html",
    "application/xml": ".xml",
    "text/xml": ".xml",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


def filename_from_headers(headers: httpx.Headers) -> str | None:
    value = headers.get("Content-Disposition", "")
    match = re.search(r"filename\*=UTF-8''([^;]+)", value, re.IGNORECASE)
    if match:
        return unquote(match.group(1)).strip('"')
    match = re.search(r'filename\s*=\s*"?([^";]+)', value, re.IGNORECASE)
    return unquote(match.group(1).strip()) if match else None


def raw_extension(content_type: str, filename: str | None, url: str) -> str:
    if filename and Path(filename).suffix:
        return Path(filename).suffix.lower()
    media_type = content_type.split(";", 1)[0].lower()
    if media_type in CONTENT_EXTENSIONS:
        return CONTENT_EXTENSIONS[media_type]
    suffix = Path(urlsplit(url).path).suffix.lower()
    return suffix if suffix and len(suffix) <= 8 else ".bin"


class CrawlStore:
    """Content-addressed raw files and an append-only JSONL manifest."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "HYU" / "raw"
        self.manifest_path = self.data_dir / "HYU" / "manifest.jsonl"

    def store_raw(self, content: bytes, extension: str) -> tuple[str, str]:
        digest = hashlib.sha256(content).hexdigest()
        path = self.raw_dir / digest[:2] / f"{digest}{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(content)
        return digest, path.relative_to(self.data_dir).as_posix()

    def append(self, record: dict[str, object]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def record_event(
        self,
        event: FetchEvent,
        *,
        site: str,
        kind: str,
        parent_uri: str | None = None,
        filename_override: str | None = None,
    ) -> dict[str, object]:
        response = event.response
        content_type = response.headers.get("Content-Type", "") if response else ""
        filename = filename_override or (
            filename_from_headers(response.headers) if response and kind == "attachment" else None
        )
        digest = None
        raw_path = None
        byte_count = 0
        if response is not None and response.status_code == 200:
            byte_count = len(response.content)
            extension = raw_extension(content_type, filename, event.url)
            digest, raw_path = self.store_raw(response.content, extension)
        uri = canonical_uri(event.url)
        record = {
            "url": event.url,
            "canonical_uri": uri,
            "doc_id": doc_id_for_url(uri),
            "site": site,
            "kind": event.kind or kind,
            "parent_uri": parent_uri,
            "status": event.status,
            "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sha256": digest,
            "bytes": byte_count,
            "content_type": content_type,
            "raw_path": raw_path,
            "filename": filename,
            "error": event.error,
        }
        self.append(record)
        return record


def read_manifest(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

