from io import BytesIO
import re

from pypdf import PdfWriter

from crawler.extract import (
    AttachmentInput,
    discover_attachments,
    discover_board_posts,
    discover_sitemap,
    extract_attachment,
    extract_document,
    filter_english_blocks,
    is_hangul_cjk,
    TextBlock,
)


def test_seoul_static_page_keeps_content_and_drops_popup(fixture_bytes):
    document = extract_document(
        fixture_bytes("seoul_summer.html"),
        "https://oia.hanyang.ac.kr/summer",
        "seoul",
    )
    assert "Hanyang International Summer School" in document["text"]
    assert "2nd Global Foreigner Job Fair" not in document["text"]


def test_seoul_trilingual_post_keeps_english_blocks_and_coverage(fixture_bytes):
    document = extract_document(
        fixture_bytes("seoul_notice_1814881_trilingual.html"),
        "https://oia.hanyang.ac.kr/notice/1814881",
        "seoul",
    )
    assert "Monthly Insurance premium" in document["text"]
    assert not any(is_hangul_cjk(char) for char in document["text"])
    assert 0.2 < document["lang_coverage"]["ratio"] < 0.8
    assert document["effective_date"] == "2026-03-01"


def test_seoul_attachment_links_are_filtered_and_canonical(fixture_bytes):
    links = discover_attachments(
        fixture_bytes("seoul_sub4_01_1814504_attachments.html"),
        "https://oia.hanyang.ac.kr/sub4_01/1814504",
        "seoul",
    )
    uris = {link["canonical_uri"] for link in links}
    assert any("file_srl=1814505" in uri for uri in uris)
    assert all("sid=" not in uri and "module_srl=" not in uri for uri in uris)
    assert not any("(Korean)" in link["filename"] for link in links)


def test_attachment_can_supply_all_useful_english_for_korean_notice(fixture_bytes):
    attachment = AttachmentInput(
        fixture_bytes("seoul_att_1813518_parttime_eng.pdf"),
        "part-time work confirmation_eng.pdf",
        "application/pdf",
        "https://oia.hanyang.ac.kr/?module=file&act=procFileDownload&file_srl=1813518",
    )
    document = extract_document(
        fixture_bytes("seoul_notice_1813514_korean_body.html"),
        "https://oia.hanyang.ac.kr/notice/1813514",
        "seoul",
        [attachment],
    )
    assert "Attachment: part-time work confirmation_eng.pdf" in document["text"]
    assert "Part-time Work Confirmation" in document["text"]


def test_erica_merged_table_repeats_combined_headers_without_boilerplate(fixture_bytes):
    document = extract_document(
        fixture_bytes("erica_s3_1_visa.html"),
        "https://global.hanyang.ac.kr/eng/s3/s3_1.php",
        "erica",
    )
    row = next(line for line in document["text"].splitlines() if "University Type: Bachelor's" in line)
    assert "Year: Year 1-2" in row
    assert "Permitted Hours / Weekdays: 10 hours" in row
    assert "Consent to the Privacy Policy" not in document["text"]
    assert "Support for International Students Visa" not in document["text"]


def test_erica_post_metadata_body_and_email_masking(fixture_bytes):
    document = extract_document(
        fixture_bytes("erica_board_s4_1_eng_wr86.html"),
        "https://global.hanyang.ac.kr/bbs/board.php?bo_table=s4_1_eng&wr_id=86",
        "erica",
    )
    assert "Jeonbuk Bank" in document["title"]
    assert document["post_date"] == "2026-11-03"
    assert "looking for foreign staff" in document["text"]
    assert "관리자" not in document["text"]
    assert "recruiter.redacted@example.org" not in document["text"]
    assert "[email]" in document["text"]


def test_erica_list_deduplicates_pinned_post_links(fixture_bytes):
    posts = discover_board_posts(
        fixture_bytes("erica_board_s4_1_eng_list.html"),
        "https://global.hanyang.ac.kr/bbs/board.php?bo_table=s4_1_eng",
    )
    assert len(posts) == len(set(posts))
    assert any("wr_id=86" in post for post in posts)


def test_sitemap_excludes_staff_and_keeps_notice(fixture_bytes):
    urls = discover_sitemap(fixture_bytes("seoul_sitemap.xml"))
    assert not any("/staff" in url for url in urls)
    assert any(re.search(r"/notice/\d+$", url) for url in urls)


def test_supported_office_attachments_and_blank_pdf(fixture_bytes):
    docx, _ = extract_attachment(
        fixture_bytes("seoul_att_1814505_forms.docx"), "forms.docx"
    )
    assert "GLOBAL KOREA SCHOLARSHIP" in "\n".join(block.text for block in docx)

    xlsx, _ = extract_attachment(
        fixture_bytes("seoul_att_1814512_departments.xlsx"), "departments.xlsx"
    )
    xlsx_text = "\n".join(block.text for block in xlsx)
    assert "Department of Architectural Engineering" in xlsx_text
    assert ": Hanyang University" in xlsx_text

    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    blocks, warnings = extract_attachment(output.getvalue(), "blank.pdf")
    assert blocks == []
    assert warnings == ["no_text_layer"]


def test_extracted_fixture_text_never_leaks_an_email_address(fixture_bytes):
    cases = [
        ("seoul_summer.html", "https://oia.hanyang.ac.kr/summer", "seoul"),
        ("seoul_notice_1814881_trilingual.html", "https://oia.hanyang.ac.kr/notice/1814881", "seoul"),
        ("erica_board_s4_1_eng_wr86.html", "https://global.hanyang.ac.kr/bbs/board.php?bo_table=s4_1_eng&wr_id=86", "erica"),
    ]
    email = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
    for filename, url, site in cases:
        document = extract_document(fixture_bytes(filename), url, site)
        assert not email.search(document["text"])


def test_record_schema_and_spans(fixture_bytes):
    document = extract_document(
        fixture_bytes("seoul_summer.html"),
        "https://oia.hanyang.ac.kr/summer",
        "seoul",
    )
    assert set(document) == {
        "doc_id", "source_uri", "site", "campus", "board", "post_id", "title",
        "post_date", "effective_date", "text", "spans", "attachments", "lang_coverage",
        "warnings", "parser_id", "source_sha256", "version_family_id", "superseded_by",
        "aliases",
    }
    for span in document["spans"]:
        assert document["text"][span["char_start"]:span["char_end"]]


def test_language_filter_keeps_contextual_neutral_and_marks_borderline():
    blocks = [
        TextBlock("This is ordinary English.", "paragraph"),
        TextBlock("2026.03.01", "paragraph"),
        TextBlock("English Greek Ελληνικά", "paragraph"),
        TextBlock("2027.03.01", "paragraph"),
        TextBlock("한국어 문장", "paragraph"),
        TextBlock("2028.03.01", "paragraph"),
    ]
    kept, warnings = filter_english_blocks(blocks)
    assert [block.text for block in kept] == [
        "This is ordinary English.", "2026.03.01", "English Greek Ελληνικά", "2027.03.01"
    ]
    assert warnings == ["borderline_lang:1"]


def test_unsupported_attachment_is_listed_and_attachment_filename_email_is_masked():
    html = b"""
        <html><head><title>English title</title></head><body><div id="content">
        <div class="rhymix_content xe_content"><p>English page body text about the guidebook download.</p></div>
        </div></body></html>
    """
    attachment = AttachmentInput(
        b"not hwp", "person@example.org guide.hwp", "application/x-hwp",
        "https://oia.hanyang.ac.kr/?module=file&act=procFileDownload&file_srl=1",
    )
    document = extract_document(html, "https://oia.hanyang.ac.kr/english", "seoul", [attachment])
    assert document["attachments"][0]["filename"] == "[email] guide.hwp"
    assert document["attachments"][0]["warnings"] == ["unsupported_attachment:.hwp"]



def test_broken_attachments_become_warnings_not_crashes():
    from crawler.extract import extract_attachment

    blocks, warnings = extract_attachment(b"<html><script>alert('x')</script></html>", "form.pdf")
    assert blocks == [] and warnings[0].startswith("attachment_parse_error:.pdf")


def test_erica_attachments_are_found_in_the_file_section_outside_the_body():
    from crawler.extract import discover_attachments

    html = (
        '<article id="bo_v"><div id="bo_v_con"><p>See the form.</p></div>'
        '<section id="bo_v_file"><ul><li><a href="https://global.hanyang.ac.kr/bbs/download.php'
        '?bo_table=s375_eng&wr_id=7&no=0&page=2">Leave form.pdf</a></li></ul></section></article>'
    ).encode()
    found = discover_attachments(html, "https://global.hanyang.ac.kr/bbs/board.php?bo_table=s375_eng&wr_id=7", "erica")
    assert [item["canonical_uri"] for item in found] == [
        "https://global.hanyang.ac.kr/bbs/download.php?bo_table=s375_eng&wr_id=7&no=0"
    ]


def test_seoul_static_page_keeps_every_content_widget_not_only_the_title():
    from crawler.extract import extract_document

    html = (
        '<html><head><title>한양대 국제처 - Exchange</title></head><body><div id="content">'
        '<div class="content_inner">'
        '<div class="rhymix_content xe_content"><article><h1>Program</h1></article></div>'
        '<div class="rhymix_content xe_content"><p>1. Student Exchange Program promotes interaction.</p></div>'
        '<div class="bh_widget_content"><p>팝업 공지</p></div>'
        '</div></div></body></html>'
    ).encode()
    document = extract_document(html, "https://oia.hanyang.ac.kr/exchange", "seoul")
    assert "Program" in document["text"]
    assert "Student Exchange Program" in document["text"]


def test_script_source_and_title_only_pages_are_not_documents():
    from crawler.extract import extract_document

    script_page = (
        '<html><head><title>한양대 국제처 - Partners</title></head><body><div id="content"><div class="content_inner">'
        "<div><script>var columns = [{ title: '순번', dataIndex: 'key' }]; var Table = antd.Table;</script></div>"
        '<p>Hanyang has partner universities in many countries around the world.</p>'
        '</div></div></body></html>'
    ).encode()
    document = extract_document(script_page, "https://oia.hanyang.ac.kr/partner", "seoul")
    assert "antd" not in document["text"] and "dataIndex" not in document["text"]

    title_only = (
        '<html><head><title>한양대 국제처 - VISA</title></head><body><div id="content"><div class="content_inner">'
        '<h1>VISA</h1><p>외국인등록 개요 신청 대상 대한민국에 입국한 날부터 90일을 초과하여 체류하려는 외국인</p>'
        '</div></div></body></html>'
    ).encode()
    assert extract_document(title_only, "https://oia.hanyang.ac.kr/visa", "seoul") is None


def test_key_value_table_rows_read_as_label_and_value():
    from bs4 import BeautifulSoup
    from crawler.extract import html_blocks

    soup = BeautifulSoup(
        "<section><table><tr><th>Available Hours</th><td>09:00 ~ 24:00</td></tr>"
        "<tr><th>Cost:</th><td>Free</td></tr></table></section>",
        "html.parser",
    )
    assert [block.text for block in html_blocks(soup.section)] == ["Available Hours: 09:00 ~ 24:00", "Cost: Free"]


def test_broken_and_run_on_emails_are_masked():
    from crawler.extract import mask_email

    text = "Mail coreaembajada@mofa.go.k\nr or gsisapply@sogang.ac.kr51, hykoica@hanyang.ac.kr. Follow @gksmentors"
    assert mask_email(text) == "Mail [email]\nr or [email], [email]. Follow @gksmentors"


def test_attachment_type_ignores_gnuboard_size_suffix_and_falls_back_to_content_type():
    from crawler.extract import attachment_extension

    assert attachment_extension("Leave of Absence Guidelines-English.pdf (4.2M)", "file/unknown") == ".pdf"
    assert attachment_extension(".docx") == ".docx"
    assert attachment_extension("Major Guidebook Download", "application/pdf") == ".pdf"
    assert attachment_extension("2. ERICA Leave of Absence English") == ""


def test_email_only_page_is_not_a_document():
    html = b"""<html><head><title>Contact</title></head><body><div id="content">
        <div class="content_inner"><p>international.office.contact@hanyang.ac.kr</p></div></div></body></html>"""
    assert extract_document(html, "https://oia.hanyang.ac.kr/contact", "seoul") is None


def test_gallery_board_listing_finds_posts():
    html = b"""<form id="fboardlist"><ul id="gall_ul"><li class="gall_li">
        <a href="https://global.hanyang.ac.kr/bbs/board.php?bo_table=s374_eng&wr_id=6&page=1">2026-2</a>
        </li></ul></form><a href="/bbs/board.php?bo_table=s4_1_eng&wr_id=9">sidebar</a>"""
    posts = discover_board_posts(html, "https://global.hanyang.ac.kr/bbs/board.php?bo_table=s374_eng&page=1")
    assert posts == ["https://global.hanyang.ac.kr/bbs/board.php?bo_table=s374_eng&wr_id=6"]
