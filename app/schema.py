# agents/app/schema.py
from typing import Optional

from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class Artifact(BaseModel):
    title: str
    markdown: str


class MessageData(BaseModel):
    session_id: str
    reply: str
    artifact: Optional[Artifact] = None
