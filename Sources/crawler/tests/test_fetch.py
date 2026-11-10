from collections import Counter

import httpx
import pytest

from crawler.fetch import CrawlStore, FetchEvent, Fetcher, RedirectNotAllowed, USER_AGENT


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_rate_limit_and_user_agent_are_applied_without_real_sleep():
    clock = FakeClock()
    starts = []
    headers = []

    def handler(request):
        starts.append(clock())
        headers.append(request.headers["User-Agent"])
        return httpx.Response(200, text="ok")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetcher = Fetcher(client, clock=clock, sleep=clock.sleep)
        for index in range(3):
            fetcher.request(f"https://example.test/{index}", allowed_hosts={"example.test"})

    assert starts == [0.0, 2.5, 5.0]
    assert headers == [USER_AGENT] * 3
    assert "@" not in USER_AGENT


def test_robots_disallowed_url_is_never_requested():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=(
                "User-agent: Yeti\nDisallow: /index/admin/\n\n"
                "User-agent: *\nDisallow: /private\n"
            ))
        return httpx.Response(200, text="should not be called")

    clock = FakeClock()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetcher = Fetcher(client, clock=clock, sleep=clock.sleep)
        response = fetcher.get(
            "https://example.test/private/record",
            allowed_hosts={"example.test"},
            kind="page",
        )
    assert response is None
    assert calls == ["/robots.txt"]
    assert fetcher.events[-1].status == "skipped_robots"


@pytest.mark.parametrize(
    ("statuses", "expected_calls"),
    [([503, 503, 200], 3), ([404], 1)],
)
def test_retry_policy_for_server_and_client_errors(statuses, expected_calls):
    calls = Counter()

    def handler(request):
        index = calls["count"]
        calls["count"] += 1
        return httpx.Response(statuses[index])

    clock = FakeClock()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = Fetcher(client, clock=clock, sleep=clock.sleep).request(
            "https://example.test/resource", allowed_hosts={"example.test"}
        )
    assert response.status_code == statuses[-1]
    assert calls["count"] == expected_calls


def test_retry_after_is_honoured():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200)

    clock = FakeClock()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = Fetcher(client, clock=clock, sleep=clock.sleep).request(
            "https://example.test/resource", allowed_hosts={"example.test"}
        )
    assert response.status_code == 200
    assert any(seconds >= 7 for seconds in clock.sleeps)


def test_connection_errors_are_retried_three_times():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("temporary", request=request)
        return httpx.Response(200)

    clock = FakeClock()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = Fetcher(client, clock=clock, sleep=clock.sleep).request(
            "https://example.test/resource", allowed_hosts={"example.test"}
        )
    assert response.status_code == 200
    assert calls == 3


def test_redirect_to_another_host_is_refused_before_request():
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return httpx.Response(302, headers={"Location": "https://outside.test/file"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RedirectNotAllowed):
            Fetcher(client, min_interval=0).request(
                "https://example.test/file", allowed_hosts={"example.test"}
            )
    assert calls == ["example.test"]


def test_starting_url_must_use_an_allowed_host():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RedirectNotAllowed):
            Fetcher(client, min_interval=0).request(
                "https://outside.test/file", allowed_hosts={"example.test"}
            )
    assert calls == 0


def test_raw_store_deduplicates_bytes_and_manifest_keeps_both_requests(tmp_path):
    store = CrawlStore(tmp_path)
    for url in ("https://example.test/a", "https://example.test/b"):
        request = httpx.Request("GET", url)
        response = httpx.Response(200, content=b"same", headers={"Content-Type": "text/html"}, request=request)
        store.record_event(FetchEvent(url, 200, response), site="seoul", kind="page")
    raw_files = list((tmp_path / "HYU" / "raw").rglob("*.*"))
    assert len(raw_files) == 1
    assert len((tmp_path / "HYU" / "manifest.jsonl").read_text().splitlines()) == 2



def test_robots_server_error_means_disallow_all():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetcher = Fetcher(client, clock=lambda: 0.0, sleep=lambda seconds: None)
        assert fetcher.get("https://oia.hanyang.ac.kr/summer", allowed_hosts={"oia.hanyang.ac.kr"}) is None
    assert set(calls) == {"/robots.txt"}
