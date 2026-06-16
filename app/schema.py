# agents/app/schema.py
from typing import Any, Optional

from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class FeedbackInput(BaseModel):
    id: str
    body: str
    anchor: dict[str, Any]


class ReviewRequest(BaseModel):
    article_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    rubrics: str = Field(..., min_length=1)
    current_content: str = Field(..., min_length=1)
    previous_content: Optional[str] = None
    feedbacks: list[FeedbackInput] = Field(default_factory=list)


class ReviewJobData(BaseModel):
    job_id: str


class AnalyzeRulesRequest(BaseModel):
    markdown: str = Field(..., min_length=1)


class AnalyzeRulesJobData(BaseModel):
    job_id: str
