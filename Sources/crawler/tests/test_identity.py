from crawler.extract import canonical_uri, doc_id_for_url


def test_seoul_page_canonical_uri_drops_paging_and_fragment():
    url = "http://OIA.HANYANG.AC.KR/notice/123?page=3&sort_index=x&order_type=desc&mid=board#c"
    assert canonical_uri(url) == "https://oia.hanyang.ac.kr/notice/123"


def test_seoul_attachment_and_redirect_share_identity():
    download = (
        "https://oia.hanyang.ac.kr/?module=file&act=procFileDownload&file_srl=77"
        "&sid=changing&module_srl=290"
    )
    redirect = "https://oia.hanyang.ac.kr/file/procFileOutput?file_srl=77&file_key=changing"
    expected = "https://oia.hanyang.ac.kr/?module=file&act=procFileDownload&file_srl=77"
    assert canonical_uri(download) == expected
    assert canonical_uri(redirect) == expected


def test_erica_board_canonical_uri_keeps_ordered_identity_fields_only():
    url = (
        "http://GLOBAL.HANYANG.AC.KR/bbs/board.php?wr_id=86&page=2"
        "&bo_table=s4_1_eng&sca=Visa#post"
    )
    assert canonical_uri(url) == (
        "https://global.hanyang.ac.kr/bbs/board.php?bo_table=s4_1_eng&wr_id=86"
    )


def test_erica_download_keeps_the_parameters_needed_to_identify_the_file():
    url = (
        "https://global.hanyang.ac.kr/bbs/download.php?bo_table=s375_eng&wr_id=10"
        "&no=2&page=3&token=changing"
    )
    assert canonical_uri(url) == (
        "https://global.hanyang.ac.kr/bbs/download.php?bo_table=s375_eng&wr_id=10&no=2"
    )


def test_doc_id_is_stable_across_non_identity_parameters():
    first = "https://oia.hanyang.ac.kr/notice/123?page=1"
    second = "https://oia.hanyang.ac.kr/notice/123?page=9#x"
    assert doc_id_for_url(first) == doc_id_for_url(second)



def test_erica_staff_directory_page_is_denied():
    from crawler.sites import get_site

    assert not get_site("erica").is_allowed("https://global.hanyang.ac.kr/eng/s1/s1_3.php")
    assert get_site("erica").is_allowed("https://global.hanyang.ac.kr/eng/s1/s1_2.php")
