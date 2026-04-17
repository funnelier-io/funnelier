"""
Shared API response schemas used across multiple modules.
"""

from pydantic import BaseModel
from typing import Any


class MessageResponse(BaseModel):
    """Generic message response for operations that return a status message."""
    message: str


class DetailResponse(BaseModel):
    """Generic response with message and optional detail payload."""
    message: str
    detail: Any = None


class StatusResponse(BaseModel):
    """Generic status response."""
    status: str
    message: str | None = None

