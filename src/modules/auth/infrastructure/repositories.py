"""
Auth Infrastructure - User Repository

SQLAlchemy-based repository for user persistence using tenant_users table.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.tenants import TenantUserModel
from src.infrastructure.database.repositories import SqlAlchemyRepository
from src.modules.auth.domain.entities import User, UserRole


class UserRepository(SqlAlchemyRepository[TenantUserModel, User]):
    """Repository for User entities backed by tenant_users table."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        super().__init__(session, tenant_id, TenantUserModel)

    def _to_entity(self, model: TenantUserModel) -> User:
        """Convert TenantUserModel to User domain entity."""
        return User(
            id=model.id,
            tenant_id=model.tenant_id,
            email=model.email,
            username=model.username or model.email,
            hashed_password=model.password_hash,
            full_name=model.name,
            role=UserRole(model.role) if model.role in [r.value for r in UserRole] else UserRole.VIEWER,
            is_active=model.is_active,
            is_approved=model.is_approved,
            last_login=model.last_login_at,
        )

    def _to_model(self, entity: User) -> TenantUserModel:
        """Convert User domain entity to TenantUserModel."""
        return TenantUserModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            email=entity.email,
            username=entity.username,
            name=entity.full_name,
            password_hash=entity.hashed_password,
            role=entity.role.value,
            is_active=entity.is_active,
            is_approved=entity.is_approved,
            last_login_at=entity.last_login,
            permissions=[],
        )

    async def get_by_email(self, email: str) -> User | None:
        """Find user by email within current tenant."""
        stmt = self._base_query().where(TenantUserModel.email == email)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_username(self, username: str) -> User | None:
        """Find user by username within current tenant."""
        stmt = self._base_query().where(TenantUserModel.username == username)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        """Find user by username or email within current tenant."""
        stmt = self._base_query().where(
            or_(
                TenantUserModel.email == identifier,
                TenantUserModel.username == identifier,
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_id_any_tenant(self, user_id: UUID) -> User | None:
        """Find user by ID across all tenants (for token resolution)."""
        stmt = select(TenantUserModel).where(TenantUserModel.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_login(self, username: str) -> User | None:
        """
        Find user by login identifier across all tenants.
        Searches by username or email.
        """
        stmt = select(TenantUserModel).where(
            or_(
                TenantUserModel.username == username,
                TenantUserModel.email == username,
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def email_exists(self, email: str, exclude_id: UUID | None = None) -> bool:
        """Check if email is already registered (across all tenants)."""
        stmt = select(func.count()).select_from(TenantUserModel).where(
            TenantUserModel.email == email,
        )
        if exclude_id:
            stmt = stmt.where(TenantUserModel.id != exclude_id)
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def username_exists(self, username: str, exclude_id: UUID | None = None) -> bool:
        """Check if username is already taken (across all tenants)."""
        stmt = select(func.count()).select_from(TenantUserModel).where(
            TenantUserModel.username == username,
        )
        if exclude_id:
            stmt = stmt.where(TenantUserModel.id != exclude_id)
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def update_last_login(self, user_id: UUID) -> None:
        """Update the last login timestamp."""
        stmt = (
            update(TenantUserModel)
            .where(TenantUserModel.id == user_id)
            .values(last_login_at=datetime.utcnow())
        )
        await self._session.execute(stmt)

    async def update_password(self, user_id: UUID, hashed_password: str) -> None:
        """Update user password hash."""
        stmt = (
            update(TenantUserModel)
            .where(TenantUserModel.id == user_id)
            .values(password_hash=hashed_password)
        )
        await self._session.execute(stmt)

    async def update_role(self, user_id: UUID, role: UserRole) -> None:
        """Update user role."""
        stmt = (
            update(TenantUserModel)
            .where(TenantUserModel.id == user_id)
            .values(role=role.value)
        )
        await self._session.execute(stmt)

    async def approve_user(self, user_id: UUID) -> None:
        """Approve a pending user."""
        stmt = (
            update(TenantUserModel)
            .where(TenantUserModel.id == user_id)
            .values(is_approved=True)
        )
        await self._session.execute(stmt)

    async def deactivate_user(self, user_id: UUID) -> None:
        """Deactivate a user."""
        stmt = (
            update(TenantUserModel)
            .where(TenantUserModel.id == user_id)
            .values(is_active=False)
        )
        await self._session.execute(stmt)

    async def activate_user(self, user_id: UUID) -> None:
        """Activate a user."""
        stmt = (
            update(TenantUserModel)
            .where(TenantUserModel.id == user_id)
            .values(is_active=True)
        )
        await self._session.execute(stmt)

    async def get_pending_users(self, tenant_id: UUID) -> list[User]:
        """Get users pending approval for a tenant."""
        stmt = select(TenantUserModel).where(
            TenantUserModel.tenant_id == tenant_id,
            TenantUserModel.is_approved == False,
            TenantUserModel.is_active == True,
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_tenant_users(
        self,
        tenant_id: UUID,
        include_inactive: bool = False,
    ) -> list[User]:
        """Get all users for a specific tenant."""
        stmt = select(TenantUserModel).where(
            TenantUserModel.tenant_id == tenant_id,
        )
        if not include_inactive:
            stmt = stmt.where(TenantUserModel.is_active == True)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update_user_profile(
        self,
        user_id: UUID,
        full_name: str | None = None,
        email: str | None = None,
    ) -> None:
        """Update user profile fields (name, email)."""
        values: dict[str, Any] = {}
        if full_name is not None:
            values["name"] = full_name
        if email is not None:
            values["email"] = email
        if values:
            stmt = (
                update(TenantUserModel)
                .where(TenantUserModel.id == user_id)
                .values(**values)
            )
            await self._session.execute(stmt)

