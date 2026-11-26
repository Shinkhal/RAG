from types import SimpleNamespace

from app.api.routes.query import _document_display_name, _summary_context_chunk


class TestDocumentDisplayName:
    def test_prefers_document_context_filename(self) -> None:
        doc = SimpleNamespace(id="doc-1", metadata_={"uploaded_filename": "fallback.pdf"})
        doc_context = {"filename": "cached-name.pdf"}

        assert _document_display_name(doc, doc_context) == "cached-name.pdf"

    def test_falls_back_to_document_metadata(self) -> None:
        doc = SimpleNamespace(id="doc-1", metadata_={"uploaded_filename": "original.pdf"})

        assert _document_display_name(doc, None) == "original.pdf"

    def test_falls_back_to_document_id(self) -> None:
        doc = SimpleNamespace(id="doc-1", metadata_={})

        assert _document_display_name(doc, None) == "doc-1"


class TestSummaryContextChunk:
    def test_uses_document_label_and_summary_marker(self) -> None:
        chunk = _summary_context_chunk("report.pdf", "full text")

        assert chunk["doc_name"] == "report.pdf"
        assert chunk["page"] == "document"
        assert chunk["chunk_id"] == "summary"
        assert chunk["content"] == "full text"
