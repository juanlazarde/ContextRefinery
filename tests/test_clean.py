from doc_preprocessor.clean import DocumentCleaner


def test_whitespace_normalization_and_blank_lines():
    cleaner = DocumentCleaner()
    text = "A\r\n\r\n\r\nB   \r\n"
    res = cleaner.clean(text)
    assert res.cleaned_text == "A\n\nB"


def test_page_number_removal():
    cleaner = DocumentCleaner()
    text = "Title\nPage 2\nBody\n3/10\n"
    res = cleaner.clean(text)
    assert "Page 2" not in res.cleaned_text
    assert "3/10" not in res.cleaned_text
    assert res.removed.page_numbers_count >= 2


def test_deduplication_stability():
    cleaner = DocumentCleaner()
    text = "Para one.\n\nPara two.\n\nPara one.\n"
    res = cleaner.clean(text)
    assert res.cleaned_text == "Para one.\n\nPara two."
    assert res.removed.duplicate_paragraphs_count == 1


def test_header_footer_detection_conservative_vs_aggressive():
    base = (
        "Confidential Memo\n"
        "Section A\n"
        "Data line\n"
        "Footer Legal\n\f"
        "Confidential Memo\n"
        "Section B\n"
        "Data line\n"
        "Footer Legal\n\f"
        "Confidential Memo\n"
        "Section C\n"
        "Data line\n"
        "Footer Legal\n"
    )
    conservative = DocumentCleaner(aggressive=False).clean(base)
    aggressive = DocumentCleaner(aggressive=True).clean(base)
    assert "Confidential Memo" not in conservative.cleaned_text
    assert "Footer Legal" not in conservative.cleaned_text
    assert len(aggressive.removed.repeated_headers) >= 1
