import re
import unicodedata
from datetime import datetime, timezone
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy.orm import Session

from app.core.errors import (
    NotFoundError,
    PayloadTooLargeError,
    UnprocessableEntityError,
    UnsupportedMediaTypeError,
)
from app.models.user import User
from app.models.workspace import KnowledgeChunk, KnowledgeDocument
from app.repositories import brand_repository
from app.repositories import knowledge_repository
from app.schemas.knowledge import KnowledgeSearchRequest, KnowledgeSearchResult
from app.services import dealership_service, embedding_service


MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_CHUNKS = 5000
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 160
EMBEDDING_BATCH_SIZE = 64


def list_documents(db: Session, dealership_id: int) -> list[KnowledgeDocument]:
    dealership_service.get_active_dealership(db, dealership_id)
    return knowledge_repository.list_documents(db, dealership_id)


def ingest_document(
    db: Session,
    dealership_id: int,
    current_user: User,
    filename: str,
    media_type: str | None,
    content: bytes,
    brand_id: int | None,
) -> KnowledgeDocument:
    dealership_service.get_active_dealership(db, dealership_id)
    if brand_id is not None:
        _ensure_active_brand(db, dealership_id, brand_id)
    if len(content) > MAX_UPLOAD_BYTES:
        raise PayloadTooLargeError("Document must be 15 MB or smaller")

    safe_filename = _safe_filename(filename)
    normalized_type, source_pages, page_count = _extract_document(
        safe_filename,
        media_type,
        content,
    )
    chunks = [
        (page_number, chunk)
        for page_number, page_text in source_pages
        for chunk in _chunk_text(page_text)
    ]
    if not chunks:
        raise UnprocessableEntityError("The document contains no indexable text")
    if len(chunks) > MAX_CHUNKS:
        raise UnprocessableEntityError(
            f"Document produces too many chunks (maximum {MAX_CHUNKS})"
        )

    vectors = _embed_in_batches([text for _, text in chunks])
    model = embedding_service.model_name()
    now = datetime.now(timezone.utc)
    document = KnowledgeDocument(
        dealership_id=dealership_id,
        brand_id=brand_id,
        uploaded_by_user_id=current_user.id,
        filename=safe_filename,
        media_type=normalized_type,
        status="ready",
        page_count=page_count,
        chunk_count=len(chunks),
        embedding_model=model,
        created_at=now,
        processed_at=now,
    )
    indexed_chunks = [
        KnowledgeChunk(
            chunk_index=index,
            content=text,
            embedding=vector,
            page_number=page_number,
        )
        for index, ((page_number, text), vector) in enumerate(
            zip(chunks, vectors, strict=True)
        )
    ]
    return knowledge_repository.create_document(db, document, indexed_chunks)


def delete_document(
    db: Session,
    dealership_id: int,
    document_id: int,
) -> None:
    dealership_service.get_active_dealership(db, dealership_id)
    document = knowledge_repository.get_document(db, dealership_id, document_id)
    if document is None:
        raise NotFoundError("Knowledge document not found")
    knowledge_repository.delete_document(db, document)


def search(
    db: Session,
    dealership_id: int,
    payload: KnowledgeSearchRequest,
) -> list[KnowledgeSearchResult]:
    dealership_service.get_active_dealership(db, dealership_id)
    if payload.brand_id is not None:
        _ensure_active_brand(db, dealership_id, payload.brand_id)

    query_vector = embedding_service.embed_texts([payload.query])[0]
    model = embedding_service.model_name()
    matches = knowledge_repository.list_searchable_chunks(
        db,
        dealership_id,
        payload.brand_id,
        model,
    )
    scored = [
        (
            embedding_service.cosine_similarity(query_vector, chunk.embedding),
            chunk,
            document,
        )
        for chunk, document in matches
    ]
    scored = [item for item in scored if item[0] > 0.05]
    scored.sort(key=lambda item: (-item[0], item[2].id, item[1].chunk_index))

    return [
        KnowledgeSearchResult(
            content=chunk.content,
            score=round(score, 4),
            document_id=document.id,
            filename=document.filename,
            brand_id=document.brand_id,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
        )
        for score, chunk, document in scored[: payload.limit]
    ]


def _ensure_active_brand(db: Session, dealership_id: int, brand_id: int) -> None:
    brand = brand_repository.get_for_dealership(db, dealership_id, brand_id)
    if brand is None or not brand.is_active or brand.is_deleted:
        raise NotFoundError("Active brand not found")


def _safe_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/").split("/")[-1].strip()
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) not in {"Cc", "Cf"}
    )
    if not normalized or len(normalized) > 255:
        raise UnprocessableEntityError("A valid document filename is required")
    return normalized


def _extract_document(
    filename: str,
    media_type: str | None,
    content: bytes,
) -> tuple[str, list[tuple[int | None, str]], int | None]:
    extension = filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
    content_type = (media_type or "").split(";", 1)[0].strip().casefold()
    if not content:
        raise UnprocessableEntityError("The document is empty")

    if extension == "pdf":
        if content_type not in {"", "application/pdf", "application/octet-stream"}:
            raise UnsupportedMediaTypeError("PDF filename and media type do not match")
        if b"%PDF-" not in content[:1024]:
            raise UnprocessableEntityError("The uploaded file is not a valid PDF")
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise UnprocessableEntityError("Encrypted PDFs are not supported")
            page_count = len(reader.pages)
            if page_count > MAX_PDF_PAGES:
                raise UnprocessableEntityError(
                    f"PDFs are limited to {MAX_PDF_PAGES} pages"
                )
            pages = [
                (index + 1, page.extract_text() or "")
                for index, page in enumerate(reader.pages)
            ]
        except PdfReadError as exc:
            raise UnprocessableEntityError(
                "The uploaded PDF could not be read"
            ) from exc
        return "application/pdf", pages, page_count

    if extension in {"txt", "md"}:
        if content_type not in {
            "",
            "text/plain",
            "text/markdown",
            "application/octet-stream",
        }:
            raise UnsupportedMediaTypeError("Text filename and media type do not match")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise UnprocessableEntityError(
                "Text documents must use UTF-8 encoding"
            ) from exc
        return "text/plain", [(None, text)], None

    raise UnsupportedMediaTypeError("Only PDF, TXT, and Markdown files are supported")


def _chunk_text(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = "".join(
        character
        for character in normalized
        if character in "\n\t" or unicodedata.category(character)[0] != "C"
    )
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + CHUNK_SIZE, len(normalized))
        if end < len(normalized):
            boundary = max(
                normalized.rfind("\n", start + CHUNK_SIZE // 2, end),
                normalized.rfind(" ", start + CHUNK_SIZE // 2, end),
            )
            if boundary > start:
                end = boundary
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return chunks


def _embed_in_batches(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        vectors.extend(
            embedding_service.embed_texts(texts[start : start + EMBEDDING_BATCH_SIZE])
        )
    return vectors
