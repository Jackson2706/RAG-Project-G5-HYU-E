from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from crawler.fetch import CrawlStore, FetchEvent
from crawler.run import build_snapshot, main


def test_dry_run_never_constructs_or_uses_transport(tmp_path, capsys):
    class ExplodingClient:
        def get(self, *args, **kwargs):
            raise AssertionError("dry-run attempted a request")

    assert main(["--site", "all", "--dry-run"], data_dir=tmp_path, client=ExplodingClient()) == 0
    output = capsys.readouterr().out
    assert "sitemap.xml" in output
    assert "count:" in output


def test_studyerica_exits_two(capsys, tmp_path):
    assert main(["--site", "studyerica", "--dry-run"], data_dir=tmp_path) == 2
    assert "studyerica is disabled until Gate G2" in capsys.readouterr().err


def test_max_pages_caps_transport_requests(tmp_path):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=(
                '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>https://oia.hanyang.ac.kr/summer</loc></url></urlset>'
            ), headers={"Content-Type": "application/xml"})
        return httpx.Response(200, text=(
            '<html><head><title>한양대 국제처 - Summer</title></head>'
            '<body><div id="content"><div class="rhymix_content xe_content"><p>English body text about the summer school programme.</p></div></div></body></html>'
        ), headers={"Content-Type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert main(["--site", "seoul", "--max-pages", "3"], data_dir=tmp_path, client=client) == 0
    assert len(calls) == 3


def _manifest_fixture_page(tmp_path, fixture_bytes):
    store = CrawlStore(tmp_path)
    url = "https://oia.hanyang.ac.kr/summer"
    request = httpx.Request("GET", url)
    response = httpx.Response(
        200,
        content=fixture_bytes("seoul_summer.html"),
        headers={"Content-Type": "text/html"},
        request=request,
    )
    store.record_event(FetchEvent(url, 200, response), site="seoul", kind="page")


def test_resume_skips_successful_manifest_uri(tmp_path, fixture_bytes):
    store = CrawlStore(tmp_path)
    url = "https://oia.hanyang.ac.kr/sitemap.xml"
    response = httpx.Response(
        200,
        content=b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>',
        headers={"Content-Type": "application/xml"},
        request=httpx.Request("GET", url),
    )
    store.record_event(FetchEvent(url, 200, response), site="seoul", kind="sitemap")
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert main(["--site", "seoul", "--resume"], data_dir=tmp_path, client=client) == 0
    assert calls == 0


def test_snapshot_is_verified_and_frozen(tmp_path, fixture_bytes):
    _manifest_fixture_page(tmp_path, fixture_bytes)
    snapshot = build_snapshot(tmp_path, datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert snapshot.name.startswith("hyu-20261110-")
    assert len(snapshot.name.rsplit("-", 1)[1]) == 8
    assert {path.name for path in snapshot.iterdir()} == {
        "documents.jsonl", "crawl_report.json", "SNAPSHOT.sha256"
    }
    for line in (snapshot / "SNAPSHOT.sha256").read_text().splitlines():
        digest, filename = line.split("  ")
        assert hashlib.sha256((snapshot / filename).read_bytes()).hexdigest() == digest
    with pytest.raises(FileExistsError):
        build_snapshot(tmp_path, datetime(2026, 11, 10, tzinfo=timezone.utc))



def test_one_failing_page_does_not_stop_the_crawl(tmp_path):
    from crawler.fetch import Fetcher
    from crawler.run import Crawler
    from crawler.sites import get_site

    def handler(request):
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if path == "/sitemap.xml":
            locs = "".join(f"<url><loc>https://oia.hanyang.ac.kr/{p}</loc></url>" for p in ("away", "boom", "summer"))
            return httpx.Response(200, text=f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>')
        if path == "/away":
            return httpx.Response(302, headers={"Location": "https://example.com/login"})
        if path == "/boom":
            raise httpx.ConnectError("down", request=request)
        return httpx.Response(200, text=(
            '<html><head><title>한양대 국제처 - Summer</title></head>'
            '<body><div id="content"><div class="rhymix_content xe_content"><p>English body text about the summer school programme.</p></div></div></body></html>'
        ), headers={"Content-Type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetcher = Fetcher(client, clock=lambda: 0.0, sleep=lambda seconds: None)
        report = Crawler(tmp_path, client=client, fetcher=fetcher).crawl([get_site("seoul")])
    assert report["sites"]["seoul"]["documents"] == 1
    assert report["sites"]["seoul"]["by_status"]["error"] == 2
    assert (tmp_path / "HYU" / "crawl_report.json").exists()
