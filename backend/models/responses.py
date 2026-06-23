"""
Pydantic response models — serialised at the router layer.

ChatResponse follows the standardised orchestrator output format:
  {
    "success"         : bool,
    "source"          : str,
    "intent"          : str,
    "data"            : list[dict],
    "insights"        : list[str],
    "response"        : str,
    "conversation_id" : str,
    "collections_used": list[str],
    "confidence"      : float,
    "latency_ms"      : int,
    "followups"       : list[str],
    "metadata"        : dict
  }
"""

from typing import Any, Optional
from pydantic import BaseModel


class ChatResponse(BaseModel):
    success: bool = True
    response: str
    conversation_id: str
    source: str = "llm"
    intent: str = "data_query"
    data: list[dict[str, Any]] = []
    insights: list[str] = []
    collections_used: list[str] = []
    confidence: float = 1.0
    latency_ms: int = 0
    followups: list[str] = []
    citations: list[str] = []  # document filenames cited in the response
    metadata: dict[str, Any] = {}
    # Pagination (populated for data_query intent)
    total_records: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 1


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class UserResponse(BaseModel):
    id: str
    name: Optional[str]
    username: str
    email: str
    role: str
    profile_pic: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    ready: bool
    version: str = "2.0.0"
    llm: Optional[dict[str, Any]] = None
    database: Optional[dict[str, Any]] = None


class DocumentResponse(BaseModel):
    key: str
    url: str
    size: int
