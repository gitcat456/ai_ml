from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )


class Source(BaseModel):
    filename: str
    document_title: str | None = None
    article: str | None = None
    section: str | None = None
    chapter: str | None = None
    page: int | None = None
    citation_label: str | None = None
    excerpt: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = []