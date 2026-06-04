from crawler.normalize.text import (
    clean_whitespace,
    normalize_address,
    normalize_name,
    sanitize_description,
)


def test_clean_whitespace_collapses_runs():
    assert clean_whitespace("  hello   world  ") == "hello world"
    assert clean_whitespace("a\n\tb") == "a b"


def test_clean_whitespace_handles_zero_width_chars():
    assert clean_whitespace("a​b‌c") == "abc"


def test_normalize_name_lowercases_and_strips_punctuation():
    assert normalize_name("Kim, Joo-hyun.") == "kim joohyun"
    assert normalize_name(" 김  작가 ") == "김 작가"


def test_normalize_name_empty():
    assert normalize_name("") == ""
    assert normalize_name("   ") == ""


def test_normalize_address_strips_korean_postal_artifacts():
    assert normalize_address("(03044) 서울 종로구 자하문로 106") == "서울 종로구 자하문로 106"
    assert normalize_address("서울특별시  종로구  자하문로 106 ") == "서울 종로구 자하문로 106"


def test_sanitize_description_removes_leaked_script_block():
    # Scraped pages leak an inline image-resize <script> (sometimes wrapped in an
    # HTML comment) into the description. Strip it whole.
    dirty = (
        "성남훈 작가의 수상 기념전입니다. "
        "<!-- /** 이미지 재조정 */ function resizeImage() { "
        'var imgObj = document.getElementById("post_area"); } -->'
    )
    assert sanitize_description(dirty) == "성남훈 작가의 수상 기념전입니다."

    dirty_script = "전시 소개. <script>function resizeImage(){var a=1;}</script> 끝."
    assert sanitize_description(dirty_script) == "전시 소개. 끝."


def test_sanitize_description_removes_email_pii():
    # A third party's personal email scraped into the text must not be republished.
    assert (
        sanitize_description("문의 핫제 칸즈(hatje cantz) 이메일 np-sung@hanmail.net 입니다")
        == "문의 핫제 칸즈(hatje cantz) 입니다"
    )
    assert sanitize_description("Email np-sung@hanmail.net here") == "here"
    # Bare email with no label is still removed.
    assert sanitize_description("연락 foo.bar@example.org 끝") == "연락 끝"


def test_sanitize_description_preserves_legit_angle_brackets_and_amp():
    # Artwork titles legitimately use angle brackets; ampersands are real text.
    # These are NOT HTML and must survive.
    assert sanitize_description("수상기념 <패 : FAIT> 전시") == "수상기념 <패 : FAIT> 전시"
    assert sanitize_description("Lee & Park 2인전") == "Lee & Park 2인전"


def test_sanitize_description_preserves_paragraphs_but_tidies_spaces():
    # Descriptions carry meaningful paragraph breaks — keep newlines, only
    # collapse horizontal whitespace and trim. (Flattening every newline to a
    # space would destroy the layout the web app renders.)
    assert sanitize_description("문단 하나.\n\n문단 둘.") == "문단 하나.\n\n문단 둘."
    assert sanitize_description("a    b\t c") == "a b c"
    assert sanitize_description("줄1   \n   줄2") == "줄1\n줄2"
    assert sanitize_description("많은\n\n\n\n빈줄") == "많은\n\n빈줄"
    assert sanitize_description("") == ""
    assert sanitize_description("   ") == ""
