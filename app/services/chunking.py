import io
import re
from typing import Iterator
from itertools import islice

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config.env_config import get_settings

# ── Supported file types ────────────────────────────────────────────
# Maps MIME types to their text-extraction functions.
# Extend this dict when adding support for new formats (docx, md, …).
SUPPORTED_MIME_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "text/plain": "text",
    "text/markdown": "text",
    "text/csv": "text",
}


def is_supported_file(content_type: str | None, filename: str | None = None) -> bool:
    """Return True if the file's MIME type (or extension fallback) is supported."""
    if content_type and content_type in SUPPORTED_MIME_TYPES:
        return True
    # Fallback: check extension when MIME is missing/generic
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in {"pdf", "txt", "md", "csv"}
    return False


def extract_text(file_data: bytes, content_type: str | None = None, filename: str | None = None) -> str:
    """Dispatch to the correct extractor based on MIME type / extension."""
    kind = SUPPORTED_MIME_TYPES.get(content_type or "")

    # Fallback to extension-based detection
    if kind is None and filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        ext_map = {"pdf": "pdf", "txt": "text", "md": "text", "csv": "text"}
        kind = ext_map.get(ext)

    if kind == "pdf":
        return extract_text_from_pdf(file_data)
    if kind == "text":
        return extract_text_from_plain(file_data)

    raise ValueError(
        f"Unsupported file type: content_type={content_type!r}, filename={filename!r}. "
        f"Supported types: {', '.join(SUPPORTED_MIME_TYPES.keys())}"
    )


# ── Extractors ──────────────────────────────────────────────────────

def extract_text_from_pdf(file_data: bytes) -> str:
    from PyPDF2 import PdfReader
    from PyPDF2.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(file_data))
    except PdfReadError as exc:
        raise ValueError(
            "The uploaded file is not a valid PDF or is corrupted. "
            "Please upload a valid .pdf file."
        ) from exc

    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)

    if not text_parts:
        raise ValueError("The PDF file contains no extractable text (it may be image-only).")

    return "\n\n".join(text_parts)


def extract_text_from_plain(file_data: bytes) -> str:
    """Decode plain-text files (txt, md, csv)."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return file_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode the text file. Please ensure it uses UTF-8 encoding.")


# ── Chunking ────────────────────────────────────────────────────────

def sliding_window_chunks(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    settings = get_settings()
    chunk_size = chunk_size or settings.max_chunk_size
    overlap = overlap or settings.chunk_overlap

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    return splitter.split_text(text)


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
