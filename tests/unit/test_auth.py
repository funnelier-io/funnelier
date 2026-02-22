"""
Tests for Auth Service
"""

import pytest
from uuid import uuid4

from src.modules.auth.domain.auth_service import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.modules.auth.domain.entities import User, UserRole


class TestPasswordHashing:
    """Tests for password hashing."""

    def test_hash_and_verify(self):
        password = "securepass123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt


class TestJWTTokens:
    """Tests for JWT token creation and decoding."""

    def test_create_and_decode_access_token(self):
        uid = uuid4()
        tid = uuid4()
        token = create_access_token(uid, tid, "admin")
        payload = decode_access_token(token)
        assert payload.sub == str(uid)
        assert payload.tenant_id == str(tid)
        assert payload.role == "admin"

    def test_create_token_pair(self):
        uid = uuid4()
        tid = uuid4()
        pair = create_token_pair(uid, tid, "viewer")
        assert pair.access_token
        assert pair.refresh_token
        assert pair.token_type == "bearer"
        assert pair.expires_in > 0

    def test_refresh_token_type(self):
        uid = uuid4()
        tid = uuid4()
        token = create_refresh_token(uid, tid, "admin")
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_access_token_type(self):
        uid = uuid4()
        tid = uuid4()
        token = create_access_token(uid, tid, "admin")
        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_decode_invalid_token(self):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token("not.a.valid.token")

    def test_decode_refresh_as_access_fails(self):
        uid = uuid4()
        tid = uuid4()
        token = create_refresh_token(uid, tid, "admin")
        with pytest.raises(ValueError, match="Not an access token"):
            decode_access_token(token)


class TestUserEntity:
    """Tests for User entity."""

    def test_user_role_hierarchy(self):
        user = User(
            tenant_id=uuid4(), email="a@b.c", username="a",
            role=UserRole.MANAGER,
        )
        assert user.has_permission(UserRole.VIEWER)
        assert user.has_permission(UserRole.SALESPERSON)
        assert user.has_permission(UserRole.MANAGER)
        assert not user.has_permission(UserRole.TENANT_ADMIN)
        assert not user.has_permission(UserRole.SUPER_ADMIN)

    def test_super_admin_has_all_permissions(self):
        user = User(
            tenant_id=uuid4(), email="a@b.c", username="a",
            role=UserRole.SUPER_ADMIN,
        )
        for role in UserRole:
            assert user.has_permission(role)

    def test_viewer_has_lowest_permissions(self):
        user = User(
            tenant_id=uuid4(), email="a@b.c", username="a",
            role=UserRole.VIEWER,
        )
        assert user.has_permission(UserRole.VIEWER)
        assert not user.has_permission(UserRole.SALESPERSON)

