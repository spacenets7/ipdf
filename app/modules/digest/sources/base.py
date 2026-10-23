from datetime import datetime
from typing import Protocol
from pydantic import BaseModel, Field


class Item(BaseModel):
    source: str
    external_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    url: str
    published: str
    raw_text: str
    tags: list[str] = Field(default_factory=list)
    pdf_url: str = ''


class Source(Protocol):
    def fetch(self, topics: list[str], since: datetime) -> list[Item]: ...
