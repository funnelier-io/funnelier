"""
Auth API Routes

Login, register, token refresh, user management, and approval flow.
All backed by PostgreSQL via UserRepository.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_tenant_id, get_db_session

from ..domain.auth_service import (
    create_token_pair,
    decode_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..domain.entities import User, UserRole
from ..infrastructure.repositories import UserRepository
from .schemas import (
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateUserRequest,
    UpdateUserRoleRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


# ============================================================================
# Helper
# ============================================================================

def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        is_approved=user.is_approved,
        last_login=user.last_login,
    )


# ============================================================================
# Auth Dependencies
# ============================================================================

async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    session: AsyncSession = Depends(get_db_session),
) -> User | None:
    """Extract current user from JWT token. Returns None if no token."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = UUID(payload.sub)
        repo = UserRepository(session, DEFAULT_TENANT_ID)
        user = await repo.get_by_id_any_tenant(user_id)
        if not user or not user.is_active:
            return None
        return user
    except Exception:
        return None


async def require_auth(
    user: Annotated[User | None, Depends(get_current_user)] = None,
) -> User:
    """Require authenticated user."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval",
        )
    return user


async def require_role(required: UserRole):
    """Factory for role-based guards."""
    async def _guard(user: Annotated[User, Depends(require_auth)]) -> User:
        if not user.has_permission(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{required.value} access required",
            )
        return user
    return _guard


async def require_admin(
    user: Annotated[User, Depends(require_auth)],
) -> User:
    """Require tenant_admin or higher."""
    if not user.has_permission(UserRole.TENANT_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_manager(
    user: Annotated[User, Depends(require_auth)],
) -> User:
    """Require manager or higher."""
    if not user.has_permission(UserRole.MANAGER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )
    return user


# ============================================================================
# Auth Endpoints
# ============================================================================

@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Authenticate user and return JWT tokens."""
    repo = UserRepository(session, DEFAULT_TENANT_ID)
    user = await repo.find_by_login(request.username)

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending admin approval",
        )

    await repo.update_last_login(user.id)
    tokens = create_token_pair(user.id, user.tenant_id, user.role.value)

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_in=tokens.expires_in,
        user=_user_to_response(user),
    )


@router.post("/login/form", response_model=TokenResponse)
async def login_form(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: AsyncSession = Depends(get_db_session),
):
    """OAuth2 form-based login (for Swagger UI)."""
    return await login(
        LoginRequest(username=form.username, password=form.password),
        session=session,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    request: RegisterRequest,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    session: AsyncSession = Depends(get_db_session),
):
    """
    Register a new user (self-signup).
    User is created with is_approved=False and must be approved by an admin.
    Super admins auto-approve their own registrations.
    """
    repo = UserRepository(session, tenant_id)

    if await repo.username_exists(request.username):
        raise HTTPException(status_code=409, detail="Username already exists")
    if await repo.email_exists(request.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        tenant_id=tenant_id,
        email=request.email,
        username=request.username,
        hashed_password=hash_password(request.password),
        full_name=request.full_name or request.username,
        role=UserRole.VIEWER,
        is_active=True,
        is_approved=False,  # Requires admin approval
    )
    user = await repo.add(user)

    tokens = create_token_pair(user.id, user.tenant_id, user.role.value)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_in=tokens.expires_in,
        user=_user_to_response(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = UUID(payload["sub"])
    repo = UserRepository(session, DEFAULT_TENANT_ID)
    user = await repo.get_by_id_any_tenant(user_id)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    tokens = create_token_pair(user.id, user.tenant_id, user.role.value)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_in=tokens.expires_in,
        user=_user_to_response(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: Annotated[User, Depends(require_auth)]):
    """Get current authenticated user."""
    return _user_to_response(user)


@router.put("/me/password")
async def change_password(
    user: Annotated[User, Depends(require_auth)],
    request: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Change password for current user."""
    if not verify_password(request.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    repo = UserRepository(session, user.tenant_id)
    await repo.update_password(user.id, hash_password(request.new_password))
    return {"message": "Password changed successfully"}


# ============================================================================
# User Management (Admin)
# ============================================================================

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
    include_inactive: bool = Query(default=False),
):
    """List all users in admin's tenant."""
    repo = UserRepository(session, admin.tenant_id)
    users = await repo.get_tenant_users(admin.tenant_id, include_inactive=include_inactive)
    return [_user_to_response(u) for u in users]


@router.get("/users/pending", response_model=list[UserResponse])
async def list_pending_users(
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
):
    """List users pending approval."""
    repo = UserRepository(session, admin.tenant_id)
    users = await repo.get_pending_users(admin.tenant_id)
    return [_user_to_response(u) for u in users]


@router.post("/users/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
):
    """Approve a pending user (admin only)."""
    repo = UserRepository(session, admin.tenant_id)
    target = await repo.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if target.is_approved:
        raise HTTPException(status_code=400, detail="User is already approved")

    await repo.approve_user(user_id)
    target.is_approved = True
    return _user_to_response(target)


@router.post("/users/{user_id}/reject", status_code=204)
async def reject_user(
    user_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
):
    """Reject and deactivate a pending user (admin only)."""
    repo = UserRepository(session, admin.tenant_id)
    target = await repo.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    await repo.deactivate_user(user_id)


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: UUID,
    request: UpdateUserRoleRequest,
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
):
    """Update a user's role (admin only)."""
    repo = UserRepository(session, admin.tenant_id)
    target = await repo.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    new_role = UserRole(request.role)

    # Only super_admin can assign super_admin
    if new_role == UserRole.SUPER_ADMIN and not admin.has_permission(UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Only super admins can assign super_admin role")

    # Can't change own role
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    await repo.update_role(user_id, new_role)
    target.role = new_role
    return _user_to_response(target)


@router.post("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
):
    """Deactivate a user (admin only)."""
    repo = UserRepository(session, admin.tenant_id)
    target = await repo.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    await repo.deactivate_user(user_id)
    target.is_active = False
    return _user_to_response(target)


@router.post("/users/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
):
    """Activate a deactivated user (admin only)."""
    repo = UserRepository(session, admin.tenant_id)
    target = await repo.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    await repo.activate_user(user_id)
    target.is_active = True
    return _user_to_response(target)


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    request: CreateUserRequest,
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new user (admin only). User is pre-approved."""
    repo = UserRepository(session, admin.tenant_id)

    if await repo.username_exists(request.username):
        raise HTTPException(status_code=409, detail="Username already exists")
    if await repo.email_exists(request.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    new_role = UserRole(request.role)
    # Only super_admin can create super_admin users
    if new_role == UserRole.SUPER_ADMIN and not admin.has_permission(UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Only super admins can create super_admin users")

    user = User(
        tenant_id=admin.tenant_id,
        email=request.email,
        username=request.username,
        hashed_password=hash_password(request.password),
        full_name=request.full_name or request.username,
        role=new_role,
        is_active=True,
        is_approved=True,  # Admin-created users are pre-approved
    )
    user = await repo.add(user)
    return _user_to_response(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UpdateUserRequest,
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
):
    """Update a user's profile (admin only)."""
    repo = UserRepository(session, admin.tenant_id)
    target = await repo.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check email uniqueness if changing email
    if request.email and request.email != target.email:
        if await repo.email_exists(request.email, exclude_id=user_id):
            raise HTTPException(status_code=409, detail="Email already registered")

    await repo.update_user_profile(
        user_id,
        full_name=request.full_name,
        email=request.email,
    )

    # Handle is_active change
    if request.is_active is not None and request.is_active != target.is_active:
        if user_id == admin.id and not request.is_active:
            raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
        if request.is_active:
            await repo.activate_user(user_id)
        else:
            await repo.deactivate_user(user_id)

    # Re-fetch updated user
    updated = await repo.get(user_id)
    return _user_to_response(updated)


@router.post("/users/{user_id}/reset-password", status_code=200)
async def reset_user_password(
    user_id: UUID,
    request: ResetPasswordRequest,
    admin: Annotated[User, Depends(require_admin)],
    session: AsyncSession = Depends(get_db_session),
):
    """Reset a user's password (admin only)."""
    repo = UserRepository(session, admin.tenant_id)
    target = await repo.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    await repo.update_password(user_id, hash_password(request.new_password))
    return {"message": "Password reset successfully"}


