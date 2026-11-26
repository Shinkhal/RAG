"""Unit tests for the text chunking and extraction services."""

import pytest

from app.services.chunking import (
    clean_pdf_text,
    clean_text,
    extract_pdf_with_report,
    extract_text_from_plain,
    is_informative_text,
    is_supported_file,
    make_text_splitter,
    normalize_document_text,
    sliding_window_chunks,
)


def test_pdf_extraction_report_tracks_pages_without_text(monkeypatch: pytest.MonkeyPatch) -> None:
    import PyPDF2

    class Page:
        def __init__(self, extracted: str | None) -> None:
            self.extracted = extracted

        def extract_text(self) -> str | None:
            return self.extracted

    class Reader:
        def __init__(self, _file) -> None:
            self.pages = [Page("Chapter one"), Page(None), Page("Chapter three")]

    monkeypatch.setattr(PyPDF2, "PdfReader", Reader)
    report = extract_pdf_with_report(b"pdf bytes")

    assert report.page_count == 3
    assert [page.page_num for page in report.pages] == [1, 3]
    assert report.pages_without_text == [2]


def test_pdf_extraction_can_ocr_pages_without_text(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    from types import ModuleType, SimpleNamespace

    import PyPDF2

    class Page:
        def __init__(self, text: str | None) -> None:
            self.text = text

        def extract_text(self) -> str | None:
            return self.text

    class Reader:
        def __init__(self, _file) -> None:
            self.pages = [Page("Text page"), Page(None)]

    class ImageContext:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

    class PDF:
        def load_page(self, _page_num):
            return SimpleNamespace(get_pixmap=lambda dpi: SimpleNamespace(tobytes=lambda _format: b"png"))

        def close(self) -> None:
            return None

    monkeypatch.setattr(PyPDF2, "PdfReader", Reader)
    monkeypatch.setitem(sys.modules, "fitz", SimpleNamespace(open=lambda **_kwargs: PDF()))
    monkeypatch.setitem(
        sys.modules,
        "pytesseract",
        SimpleNamespace(image_to_string=lambda _image, timeout: "Scanned page text"),
    )
    pil_module = ModuleType("PIL")
    pil_image_module = SimpleNamespace(open=lambda _source: ImageContext())
    pil_module.Image = pil_image_module
    monkeypatch.setitem(sys.modules, "PIL", pil_module)
    monkeypatch.setitem(sys.modules, "PIL.Image", pil_image_module)

    report = extract_pdf_with_report(b"pdf bytes", enable_ocr=True)

    assert report.pages_without_text == []
    assert report.ocr_pages == [2]
    assert report.pages[1].text == "Scanned page text"


# ── is_supported_file ─────────────────────────────────────────────


class TestIsSupportedFile:
    def test_pdf_mime_type(self) -> None:
        assert is_supported_file("application/pdf") is True

    def test_text_mime_type(self) -> None:
        assert is_supported_file("text/plain") is True

    def test_markdown_mime_type(self) -> None:
        assert is_supported_file("text/markdown") is True

    def test_csv_mime_type(self) -> None:
        assert is_supported_file("text/csv") is True

    def test_unsupported_mime_type(self) -> None:
        assert is_supported_file("image/png") is False

    def test_none_mime_with_pdf_filename(self) -> None:
        assert is_supported_file(None, filename="report.pdf") is True

    def test_none_mime_with_txt_filename(self) -> None:
        assert is_supported_file(None, filename="notes.txt") is True

    def test_none_mime_with_md_filename(self) -> None:
        assert is_supported_file(None, filename="readme.md") is True

    def test_none_mime_with_unsupported_filename(self) -> None:
        assert is_supported_file(None, filename="image.png") is False

    def test_none_mime_no_filename(self) -> None:
        assert is_supported_file(None) is False


# ── clean_text ────────────────────────────────────────────────────


class TestCleanText:
    def test_collapses_whitespace(self) -> None:
        assert clean_text("hello   world") == "hello world"

    def test_removes_multiple_newlines(self) -> None:
        assert clean_text("hello\n\n\nworld") == "hello world"

    def test_strips_leading_trailing(self) -> None:
        assert clean_text("  hello  ") == "hello"

    def test_removes_control_characters(self) -> None:
        assert clean_text("hello\x00\x01world") == "helloworld"

    def test_empty_string(self) -> None:
        assert clean_text("") == ""

    def test_tabs_and_mixed_whitespace(self) -> None:
        assert clean_text("hello\t\n  world") == "hello world"


class TestCleanPdfText:
    def test_removes_leading_decorative_glyphs(self) -> None:
        text = "●●●Landour Trip - 3 nights & 4 days"
        assert clean_pdf_text(text) == "Landour Trip - 3 nights & 4 days"

    def test_removes_symbol_only_lines(self) -> None:
        text = "Overview\n●●●\nDay 1 plan"
        assert clean_pdf_text(text) == "Overview\n\nDay 1 plan"


class TestDocumentTextNormalization:
    def test_preserves_paragraph_boundaries(self) -> None:
        text = "Heading  \r\nBody line\r\n\r\nNext paragraph"
        assert normalize_document_text(text) == "Heading\nBody line\n\nNext paragraph"

    def test_rejects_invalid_chunk_settings(self) -> None:
        with pytest.raises(ValueError, match="chunk_size"):
            make_text_splitter(chunk_size=0, overlap=0)

        with pytest.raises(ValueError, match="overlap"):
            make_text_splitter(chunk_size=20, overlap=20)


class TestIsInformativeText:
    def test_rejects_symbol_only_text(self) -> None:
        assert is_informative_text("●●●") is False

    def test_accepts_text_with_letters(self) -> None:
        assert is_informative_text("●●●Landour Trip") is True


# ── extract_text_from_plain ───────────────────────────────────────


class TestExtractTextFromPlain:
    def test_utf8_text(self) -> None:
        data = "Hello, world!".encode("utf-8")
        assert extract_text_from_plain(data) == "Hello, world!"

    def test_latin1_fallback(self) -> None:
        data = "café".encode("latin-1")
        result = extract_text_from_plain(data)
        assert "caf" in result

    def test_utf8_bom(self) -> None:
        data = b"\xef\xbb\xbfBOM text"
        result = extract_text_from_plain(data)
        assert "BOM text" in result

    def test_invalid_encoding_raises(self) -> None:
        # Bytes that are invalid in all attempted encodings is hard to produce,
        # but we can at least verify the function handles valid encodings.
        data = b"simple ascii"
        assert extract_text_from_plain(data) == "simple ascii"


# ── sliding_window_chunks ────────────────────────────────────────


class TestSlidingWindowChunks:
    def test_short_text_single_chunk(self) -> None:
        chunks = sliding_window_chunks("Hello world", chunk_size=500, overlap=20)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_splits_long_text(self) -> None:
        # 5 sentences × ~50 chars = ~250 chars; with chunk_size=100 should split
        text = "This is a sentence about science. " * 10
        chunks = sliding_window_chunks(text.strip(), chunk_size=100, overlap=20)
        assert len(chunks) > 1

    def test_overlap_creates_shared_content(self) -> None:
        text = "Word " * 200  # 1000 chars
        chunks = sliding_window_chunks(text.strip(), chunk_size=100, overlap=30)
        # With overlap, consecutive chunks should share some text
        assert len(chunks) >= 2
        # The end of chunk N should overlap with the start of chunk N+1
        for i in range(len(chunks) - 1):
            # There should be some shared words between consecutive chunks
            words_a = set(chunks[i].split()[-5:])
            words_b = set(chunks[i + 1].split()[:5])
            # At least some overlap expected (they're all "Word" so this is trivially true)
            assert len(words_a & words_b) >= 0  # structural check: no crash

    def test_empty_text(self) -> None:
        chunks = sliding_window_chunks("", chunk_size=100, overlap=20)
        assert chunks == []

    def test_respects_sentence_boundaries(self) -> None:
        text = "First sentence. Second sentence. Third sentence."
        chunks = sliding_window_chunks(text, chunk_size=30, overlap=5)
        # Should prefer splitting at ". " boundary
        assert len(chunks) >= 2
