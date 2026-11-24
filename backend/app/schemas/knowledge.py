from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeDocumentResponse(BaseModel):
    id: int
    dealership_id: int
    brand_id: int | None
    uploaded_by_user_id: int
    filename: str
    media_type: str
    status: str
    page_count: int | None
    chunk_count: int
    created_at: datetime
    processed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    brand_id: int | None = Field(default=None, ge=1)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError(
                "query must contain at least two non-whitespace characters"
            )
        return value


class KnowledgeSearchResult(BaseModel):
    content: str
    score: float
    document_id: int
    filename: str
    brand_id: int | None
    page_number: int | None
    chunk_index: int
