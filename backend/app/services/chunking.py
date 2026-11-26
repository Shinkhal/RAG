import io
import re
from itertools import islice
from typing import Iterator, NamedTuple

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config.env_config import get_settings

SUPPORTED_MIME_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "text/plain": "text",
    "text/markdown": "text",
    "text/csv": "text",
}


class ExtractedPage(NamedTuple):
    page_num: int
    text: str


class PDFExtractionReport(NamedTuple):
    pages: list[ExtractedPage]
    page_count: int
    pages_without_text: list[int]
    ocr_pages: list[int]


_PDF_DECORATIVE_GLYPHS = "\u25cf\u25cb\u2022\u25e6\u25a0\u25a1\uf0b7"


def is_supported_file(content_type: str | None, filename: str | None = None) -> bool:
    if content_type and content_type in SUPPORTED_MIME_TYPES:
        return True
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in {"pdf", "txt", "md", "csv"}
    return False


def extract_text(
    file_data: bytes, content_type: str | None = None, filename: str | None = None
) -> str:
    kind = SUPPORTED_MIME_TYPES.get(content_type or "")

    if kind is None and filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        ext_map = {"pdf": "pdf", "txt": "text", "md": "text", "csv": "text"}
        kind = ext_map.get(ext)

    if kind == "pdf":
        pages = extract_pages_from_pdf(file_data)
        return "\n\n".join(p.text for p in pages)

    if kind == "text":
        return extract_text_from_plain(file_data)

    raise ValueError(
        f"Unsupported file type: content_type={content_type!r}, filename={filename!r}. "
        f"Supported types: {', '.join(SUPPORTED_MIME_TYPES.keys())}"
    )


def extract_pages_from_pdf(file_data: bytes) -> list[ExtractedPage]:
    return extract_pdf_with_report(file_data).pages


def extract_pdf_with_report(file_data: bytes, enable_ocr: bool = False) -> PDFExtractionReport:
    from PyPDF2 import PdfReader
    from PyPDF2.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(file_data))
    except PdfReadError as exc:
        raise ValueError(
            "The uploaded file is not a valid PDF or is corrupted. Please upload a valid .pdf file."
        ) from exc

    pages: list[ExtractedPage] = []
    pages_without_text: list[int] = []
    ocr_pages: list[int] = []
    missing_page_numbers: list[int] = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if text:
            cleaned = clean_pdf_text(text)
            if cleaned:
                pages.append(ExtractedPage(page_num=page_num, text=cleaned))
            else:
                missing_page_numbers.append(page_num)
        else:
            missing_page_numbers.append(page_num)

    if enable_ocr and missing_page_numbers:
        try:
            import fitz
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "PDF OCR is enabled but PyMuPDF, Pillow, or pytesseract is not installed"
            ) from exc

        pdf = fitz.open(stream=file_data, filetype="pdf")
        try:
            for page_num in missing_page_numbers:
                pixmap = pdf.load_page(page_num - 1).get_pixmap(dpi=200)
                with Image.open(io.BytesIO(pixmap.tobytes("png"))) as image:
                    ocr_text = pytesseract.image_to_string(image, timeout=45)
                cleaned = clean_pdf_text(ocr_text)
                if cleaned:
                    pages.append(ExtractedPage(page_num=page_num, text=cleaned))
                    ocr_pages.append(page_num)
        finally:
            pdf.close()

    extracted_page_numbers = {page.page_num for page in pages}
    pages_without_text = [
        page_num for page_num in range(1, len(reader.pages) + 1)
        if page_num not in extracted_page_numbers
    ]

    if not pages:
        raise ValueError("The PDF file contains no extractable text (it may be image-only).")

    pages.sort(key=lambda page: page.page_num)
    return PDFExtractionReport(pages, len(reader.pages), pages_without_text, ocr_pages)


def extract_text_from_pdf(file_data: bytes) -> str:
    pages = extract_pages_from_pdf(file_data)
    return "\n\n".join(p.text for p in pages)


def extract_text_from_plain(file_data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return file_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode the text file. Please ensure it uses UTF-8 encoding.")


def normalize_document_text(text: str) -> str:
    """Normalize extracted text while preserving paragraph and line boundaries."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)
    return text.strip()


def make_text_splitter(
    chunk_size: int | None = None, overlap: int | None = None
) -> RecursiveCharacterTextSplitter:
    """Create a character-based splitter with validated configured limits."""
    settings = get_settings()
    chunk_size = settings.max_chunk_size if chunk_size is None else chunk_size
    overlap = settings.chunk_overlap if overlap is None else overlap
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def sliding_window_chunks(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    return make_text_splitter(chunk_size, overlap).split_text(text)


def clean_pdf_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(rf"^[\s{re.escape(_PDF_DECORATIVE_GLYPHS)}]+(?=[A-Za-z0-9])", "", text)
    text = re.sub(
        rf"(?m)^[{re.escape(_PDF_DECORATIVE_GLYPHS)}\s]+$",
        "",
        text,
    )
    return normalize_document_text(text)


def is_informative_text(text: str) -> bool:
    """Return True when text contains at least one letter or digit.

    ``str.isalnum`` is Unicode-aware, so documents written in non-Latin
    scripts (Hindi, Arabic, CJK, ...) are not discarded during ingestion.
    """
    return any(character.isalnum() for character in text)


def batched(items: list[str], size: int | None = None) -> Iterator[list[str]]:
    settings = get_settings()
    size = size or settings.embedding_batch_size

    it = iter(items)
    while batch := list(islice(it, size)):
        yield batch


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()
