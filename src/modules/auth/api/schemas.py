"""
Auth API Schemas
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str = Field(min_length=8)
    full_name: str = ""


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    username: str
    full_name: str
    role: str
    is_active: bool
    is_approved: bool = True
    last_login: datetime | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(pattern="^(super_admin|tenant_admin|manager|salesperson|viewer)$")


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    is_active: bool | None = None

