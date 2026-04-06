"""
Unit Tests for Phase 22: User Management

Tests for auth schemas, entities, and role hierarchy.
"""

import pytest
from uuid import uuid4, UUID

from src.modules.auth.domain.entities import User, UserRole
from src.modules.auth.api.schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    ResetPasswordRequest,
    UpdateUserRoleRequest,
    UserResponse,
)


# ============================================================================
# UserRole tests
# ============================================================================

class TestUserRole:
    """Tests for UserRole enum."""

    def test_all_roles_exist(self):
        roles = [r.value for r in UserRole]
        assert "super_admin" in roles
        assert "tenant_admin" in roles
        assert "manager" in roles
        assert "salesperson" in roles
        assert "viewer" in roles

    def test_role_count(self):
        assert len(UserRole) == 5


# ============================================================================
# User entity tests
# ============================================================================

class TestUser:
    """Tests for User entity."""

    def _make_user(self, role: UserRole = UserRole.VIEWER, **kwargs) -> User:
        return User(
            id=uuid4(),
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            email="test@example.com",
            username="testuser",
            hashed_password="hashed",
            full_name="Test User",
            role=role,
            is_active=True,
            is_approved=True,
            **kwargs,
        )

    def test_super_admin_has_all_permissions(self):
        user = self._make_user(UserRole.SUPER_ADMIN)
        assert user.has_permission(UserRole.SUPER_ADMIN)
        assert user.has_permission(UserRole.TENANT_ADMIN)
        assert user.has_permission(UserRole.MANAGER)
        assert user.has_permission(UserRole.SALESPERSON)
        assert user.has_permission(UserRole.VIEWER)

    def test_viewer_has_only_viewer_permission(self):
        user = self._make_user(UserRole.VIEWER)
        assert user.has_permission(UserRole.VIEWER)
        assert not user.has_permission(UserRole.SALESPERSON)
        assert not user.has_permission(UserRole.MANAGER)
        assert not user.has_permission(UserRole.TENANT_ADMIN)
        assert not user.has_permission(UserRole.SUPER_ADMIN)

    def test_manager_hierarchy(self):
        user = self._make_user(UserRole.MANAGER)
        assert user.has_permission(UserRole.VIEWER)
        assert user.has_permission(UserRole.SALESPERSON)
        assert user.has_permission(UserRole.MANAGER)
        assert not user.has_permission(UserRole.TENANT_ADMIN)
        assert not user.has_permission(UserRole.SUPER_ADMIN)

    def test_tenant_admin_hierarchy(self):
        user = self._make_user(UserRole.TENANT_ADMIN)
        assert user.has_permission(UserRole.VIEWER)
        assert user.has_permission(UserRole.SALESPERSON)
        assert user.has_permission(UserRole.MANAGER)
        assert user.has_permission(UserRole.TENANT_ADMIN)
        assert not user.has_permission(UserRole.SUPER_ADMIN)

    def test_salesperson_hierarchy(self):
        user = self._make_user(UserRole.SALESPERSON)
        assert user.has_permission(UserRole.VIEWER)
        assert user.has_permission(UserRole.SALESPERSON)
        assert not user.has_permission(UserRole.MANAGER)

    def test_user_defaults(self):
        user = User(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            email="x@x.com",
            username="x",
        )
        assert user.role == UserRole.VIEWER
        assert user.is_active is True
        assert user.is_approved is False
        assert user.last_login is None
        assert user.full_name == ""


# ============================================================================
# Schema tests
# ============================================================================

class TestCreateUserRequest:
    """Tests for CreateUserRequest schema."""

    def test_valid_request(self):
        req = CreateUserRequest(
            email="admin@test.com",
            username="admin",
            password="securepass123",
            full_name="Admin User",
            role="tenant_admin",
        )
        assert req.email == "admin@test.com"
        assert req.role == "tenant_admin"

    def test_default_role_is_viewer(self):
        req = CreateUserRequest(
            email="test@test.com",
            username="test",
            password="securepass123",
        )
        assert req.role == "viewer"

    def test_short_password_rejected(self):
        with pytest.raises(Exception):
            CreateUserRequest(
                email="test@test.com",
                username="test",
                password="short",
            )

    def test_invalid_role_rejected(self):
        with pytest.raises(Exception):
            CreateUserRequest(
                email="test@test.com",
                username="test",
                password="securepass123",
                role="god_mode",
            )


class TestUpdateUserRequest:
    """Tests for UpdateUserRequest schema."""

    def test_partial_update(self):
        req = UpdateUserRequest(full_name="New Name")
        assert req.full_name == "New Name"
        assert req.email is None
        assert req.is_active is None

    def test_all_fields(self):
        req = UpdateUserRequest(
            full_name="Updated",
            email="new@email.com",
            is_active=False,
        )
        assert req.full_name == "Updated"
        assert req.email == "new@email.com"
        assert req.is_active is False


class TestResetPasswordRequest:
    """Tests for ResetPasswordRequest schema."""

    def test_valid_password(self):
        req = ResetPasswordRequest(new_password="newpass123")
        assert req.new_password == "newpass123"

    def test_short_password_rejected(self):
        with pytest.raises(Exception):
            ResetPasswordRequest(new_password="short")


class TestUpdateUserRoleRequest:
    """Tests for UpdateUserRoleRequest schema."""

    def test_valid_roles(self):
        for role in ["super_admin", "tenant_admin", "manager", "salesperson", "viewer"]:
            req = UpdateUserRoleRequest(role=role)
            assert req.role == role

    def test_invalid_role_rejected(self):
        with pytest.raises(Exception):
            UpdateUserRoleRequest(role="hacker")


class TestUserResponse:
    """Tests for UserResponse schema."""

    def test_full_response(self):
        resp = UserResponse(
            id=uuid4(),
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            email="test@test.com",
            username="testuser",
            full_name="Test User",
            role="manager",
            is_active=True,
            is_approved=True,
            last_login=None,
        )
        assert resp.role == "manager"
        assert resp.is_approved is True

    def test_response_with_defaults(self):
        resp = UserResponse(
            id=uuid4(),
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            email="test@test.com",
            username="testuser",
            full_name="Test",
            role="viewer",
            is_active=True,
        )
        assert resp.is_approved is True  # default
        assert resp.last_login is None

