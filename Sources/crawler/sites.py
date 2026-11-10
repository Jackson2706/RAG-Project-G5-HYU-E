"""Crawl scope and selectors for the approved HYU sites."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urljoin, urlsplit


COMMON_DENY_PATTERNS = (
    r"/staff(?:[/?]|$)",
    r"/bbs/write\.php",
    r"(?:[?&])bo_table=(?:s4_3_eng|s354_eng)(?:&|$)",
    r"/index/(?:admin|adm)/",
)


@dataclass(frozen=True)
class SiteConfig:
    name: str
    campus: str
    base_url: str
    enabled: bool
    disabled_reason: str | None
    seeds: tuple[str, ...]
    allow_patterns: tuple[str, ...]
    deny_patterns: tuple[str, ...]
    content_selector: str
    drop_selectors: tuple[str, ...]
    parser_id: str

    @property
    def allowed_hosts(self) -> frozenset[str]:
        return frozenset({urlsplit(self.base_url).hostname or ""})

    def is_allowed(self, url: str) -> bool:
        absolute = urljoin(self.base_url, url)
        parsed = urlsplit(absolute)
        if (parsed.hostname or "").lower() not in self.allowed_hosts:
            return False
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        if any(re.search(pattern, target, re.IGNORECASE) for pattern in self.deny_patterns):
            return False
        return any(re.search(pattern, target, re.IGNORECASE) for pattern in self.allow_patterns)


SEOUL = SiteConfig(
    name="seoul",
    campus="seoul",
    base_url="https://oia.hanyang.ac.kr",
    enabled=True,
    disabled_reason=None,
    seeds=("https://oia.hanyang.ac.kr/sitemap.xml",),
    allow_patterns=(
        r"^/sitemap\.xml$",
        r"^/(?:notice|sub4_01|Forms)/\d+/?$",
        r"^/(?!file/)[A-Za-z0-9_./-]+/?$",
        r"^/\?(?=.*\bmodule=file)(?=.*\bfile_srl=\d+)",
        r"^/file/procFileOutput\?(?=.*\bfile_srl=\d+)",
    ),
    deny_patterns=COMMON_DENY_PATTERNS,
    content_selector=(
        ".content_body .rhymix_content.xe_content, "
        "#content .rhymix_content.xe_content"
    ),
    drop_selectors=(
        "header.header_wrap",
        '[class*="bh_layer"]',
        ".bh_widget_content",
        "#board_list",
        ".content_footer",
        "ul.document_nav",
        ".footer",
    ),
    parser_id="seoul-rhymix-v1",
)

ERICA_BOARD_NAMES = ("s4_1_eng", "s374_eng", "s375_eng", "s4_2_eng")

ERICA = SiteConfig(
    name="erica",
    campus="erica",
    base_url="https://global.hanyang.ac.kr",
    enabled=True,
    disabled_reason=None,
    seeds=(
        "https://global.hanyang.ac.kr/eng/",
        *(f"https://global.hanyang.ac.kr/bbs/board.php?bo_table={name}" for name in ERICA_BOARD_NAMES),
    ),
    allow_patterns=(
        r"^/eng/(?:$|s[123]/[^?]+\.php$)",
        r"^/bbs/board\.php\?",
        r"^/bbs/download\.php\?",
    ),
    deny_patterns=COMMON_DENY_PATTERNS,
    content_selector=".sub-cnt > section, #bo_v_con",
    drop_selectors=(
        "header#header",
        "#gnb",
        "#clone_gnb",
        ".gn-2dep",
        "#footer.footer",
        ".layer_box.layer_privacy",
        ".main-board",
        ".sub-info",
        "#bo_v_info",
        ".btn_area",
    ),
    parser_id="erica-gnuboard-v1",
)

STUDYERICA = SiteConfig(
    name="studyerica",
    campus="erica",
    base_url="https://studyerica.hanyang.ac.kr",
    enabled=False,
    disabled_reason="after Gate G2",
    seeds=("https://studyerica.hanyang.ac.kr/eng/",),
    allow_patterns=(r"^/eng/",),
    deny_patterns=COMMON_DENY_PATTERNS,
    content_selector="main",
    drop_selectors=(),
    parser_id="studyerica-disabled-v1",
)

SITES = {site.name: site for site in (SEOUL, ERICA, STUDYERICA)}


def get_site(name: str) -> SiteConfig:
    return SITES[name]


def site_for_url(url: str) -> SiteConfig | None:
    host = (urlsplit(url).hostname or "").lower()
    return next((site for site in SITES.values() if host in site.allowed_hosts), None)


def is_board_listing(url: str) -> bool:
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    return parsed.path == "/bbs/board.php" and "bo_table" in query and "wr_id" not in query

