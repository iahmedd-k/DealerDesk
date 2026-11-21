from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace import KnowledgeChunk, KnowledgeDocument


def create_document(
    db: Session,
    document: KnowledgeDocument,
    chunks: list[KnowledgeChunk],
) -> KnowledgeDocument:
    db.add(document)
    db.flush()
    for chunk in chunks:
        chunk.document_id = document.id
    db.add_all(chunks)
    db.commit()
    db.refresh(document)
    return document


def list_documents(db: Session, dealership_id: int) -> list[KnowledgeDocument]:
    statement = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.dealership_id == dealership_id)
        .order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.id.desc())
    )
    return list(db.scalars(statement))


def get_document(
    db: Session,
    dealership_id: int,
    document_id: int,
) -> KnowledgeDocument | None:
    return db.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.dealership_id == dealership_id,
        )
    )


def delete_document(db: Session, document: KnowledgeDocument) -> None:
    db.delete(document)
    db.commit()


def list_searchable_chunks(
    db: Session,
    dealership_id: int,
    brand_id: int | None,
    embedding_model: str,
) -> list[tuple[KnowledgeChunk, KnowledgeDocument]]:
    statement = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(
            KnowledgeDocument,
            KnowledgeDocument.id == KnowledgeChunk.document_id,
        )
        .where(
            KnowledgeDocument.dealership_id == dealership_id,
            KnowledgeDocument.status == "ready",
            KnowledgeDocument.embedding_model == embedding_model,
        )
    )
    if brand_id is None:
        statement = statement.where(KnowledgeDocument.brand_id.is_(None))
    else:
        statement = statement.where(
            KnowledgeDocument.brand_id.is_(None)
            | (KnowledgeDocument.brand_id == brand_id)
        )
    return list(db.execute(statement).tuples())
