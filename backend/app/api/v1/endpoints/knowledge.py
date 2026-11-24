from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, STAFF_ROLES
from app.db.session import get_db
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.models.workspace import KnowledgeDocument
from app.schemas.knowledge import (
    KnowledgeDocumentResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
)
from app.services import knowledge_service


router = APIRouter(
    prefix="/dealerships/{dealership_id}/knowledge",
    tags=["Dealership Knowledge"],
)


@router.get(
    "/documents",
    response_model=list[KnowledgeDocumentResponse],
    summary="List dealership knowledge documents",
)
def list_documents(
    dealership_id: int,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[KnowledgeDocument]:
    return knowledge_service.list_documents(db, dealership_id)


@router.post(
    "/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a dealership document",
)
def upload_document(
    dealership_id: int,
    file: UploadFile = File(...),
    brand_id: int | None = Form(default=None, ge=1),
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> KnowledgeDocument:
    content = file.file.read(knowledge_service.MAX_UPLOAD_BYTES + 1)
    return knowledge_service.ingest_document(
        db,
        dealership_id,
        current_user,
        file.filename or "",
        file.content_type,
        content,
        brand_id,
    )


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a dealership knowledge document",
)
def delete_document(
    dealership_id: int,
    document_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    knowledge_service.delete_document(db, dealership_id, document_id)


@router.post(
    "/search",
    response_model=list[KnowledgeSearchResult],
    summary="Retrieve brand-scoped knowledge with source metadata",
)
def search_knowledge(
    dealership_id: int,
    payload: KnowledgeSearchRequest,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[KnowledgeSearchResult]:
    return knowledge_service.search(db, dealership_id, payload)
