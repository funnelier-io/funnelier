"""
Auth API Routes

Login, register, token refresh, and user management.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from src.api.dependencies import get_current_tenant_id

from ..domain.auth_service import (
    create_token_pair,
    decode_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..domain.entities import User, UserRole
from .schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# ── In-memory user store (will be replaced by DB repository) ──
_users: dict[str, User] = {}


def _seed_default_admin():
    """Seed a default admin user for development."""
    if "admin" not in _users:
        admin = User(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            email="admin@funnelier.ir",
            username="admin",
            hashed_password=hash_password("admin1234"),
            full_name="مدیر سیستم",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        _users["admin"] = admin


_seed_default_admin()


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        last_login=user.last_login,
    )


# ============================================================================
# Auth Dependency
# ============================================================================

async def get_current_user(token: Annotated[str | None, Depends(oauth2_scheme)] = None) -> User | None:
    """Extract current user from JWT token. Returns None if no token."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        username_or_id = payload.sub
        # Look up by user ID or username
        for user in _users.values():
            if str(user.id) == username_or_id or user.username == username_or_id:
                if not user.is_active:
                    return None
                return user
        return None
    except Exception:
        return None


async def require_auth(user: Annotated[User | None, Depends(get_current_user)] = None) -> User:
    """Require authenticated user."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(user: Annotated[User, Depends(require_auth)]) -> User:
    """Require admin role."""
    if not user.has_permission(UserRole.TENANT_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


# ============================================================================
# Auth Endpoints
# ============================================================================

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT tokens."""
    user = _users.get(request.username)
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

    user.last_login = datetime.utcnow()
    tokens = create_token_pair(user.id, user.tenant_id, user.role.value)

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_in=tokens.expires_in,
        user=_user_to_response(user),
    )


@router.post("/login/form", response_model=TokenResponse)
async def login_form(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """OAuth2 form-based login (for Swagger UI)."""
    return await login(LoginRequest(username=form.username, password=form.password))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    request: RegisterRequest,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Register a new user."""
    if request.username in _users:
        raise HTTPException(status_code=409, detail="Username already exists")

    # Check email uniqueness
    for u in _users.values():
        if u.email == request.email:
            raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        tenant_id=tenant_id,
        email=request.email,
        username=request.username,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        role=UserRole.VIEWER,
        is_active=True,
    )
    _users[request.username] = user

    tokens = create_token_pair(user.id, user.tenant_id, user.role.value)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_in=tokens.expires_in,
        user=_user_to_response(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload["sub"]
    for user in _users.values():
        if str(user.id) == user_id:
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

    raise HTTPException(status_code=401, detail="User not found")


@router.get("/me", response_model=UserResponse)
async def get_me(user: Annotated[User, Depends(require_auth)]):
    """Get current authenticated user."""
    return _user_to_response(user)


@router.put("/me/password")
async def change_password(
    user: Annotated[User, Depends(require_auth)],
    request: ChangePasswordRequest,
):
    """Change password for current user."""
    if not verify_password(request.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(request.new_password)
    return {"message": "Password changed successfully"}


@router.get("/users", response_model=list[UserResponse])
async def list_users(admin: Annotated[User, Depends(require_admin)]):
    """List all users (admin only)."""
    return [_user_to_response(u) for u in _users.values() if u.tenant_id == admin.tenant_id]

