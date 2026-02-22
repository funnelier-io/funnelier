"""
Auth Domain Entities

User entity for authentication and authorization.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.core.domain import TenantEntity


class UserRole(str, Enum):
    """User roles for RBAC."""
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    MANAGER = "manager"
    SALESPERSON = "salesperson"
    VIEWER = "viewer"


class User(TenantEntity[UUID]):
    """User entity."""
    id: UUID = Field(default_factory=uuid4)
    email: str
    username: str
    hashed_password: str = ""
    full_name: str = ""
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    last_login: datetime | None = None

    def has_permission(self, required_role: UserRole) -> bool:
        """Check if user has required role or higher."""
        role_hierarchy = {
            UserRole.SUPER_ADMIN: 5,
            UserRole.TENANT_ADMIN: 4,
            UserRole.MANAGER: 3,
            UserRole.SALESPERSON: 2,
            UserRole.VIEWER: 1,
        }
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(required_role, 0)

