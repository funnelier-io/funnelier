"""
Core Domain - Base Entities and Value Objects
Following DDD principles for the shared kernel
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


# Type variable for generic entity ID
TId = TypeVar("TId", bound=UUID | int | str)


class ValueObject(BaseModel):
    """
    Base class for Value Objects.
    Value Objects are immutable and compared by their attributes.
    """

    model_config = ConfigDict(frozen=True)


class Entity(BaseModel, Generic[TId]):
    """
    Base class for Entities.
    Entities have identity and are compared by their ID.
    """

    id: TId
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class AggregateRoot(Entity[TId]):
    """
    Base class for Aggregate Roots.
    Aggregate Roots are the entry point to an aggregate and manage domain events.
    """

    _domain_events: list["DomainEvent"] = []

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._domain_events = []

    def add_domain_event(self, event: "DomainEvent") -> None:
        """Add a domain event to be published."""
        self._domain_events.append(event)

    def clear_domain_events(self) -> list["DomainEvent"]:
        """Clear and return all domain events."""
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events

    @property
    def domain_events(self) -> list["DomainEvent"]:
        """Get pending domain events."""
        return self._domain_events.copy()


class DomainEvent(BaseModel):
    """
    Base class for Domain Events.
    Events represent something that happened in the domain.
    """

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    aggregate_id: UUID | str | int
    aggregate_type: str
    tenant_id: UUID

    model_config = ConfigDict(frozen=True)


class TenantEntity(Entity[TId]):
    """
    Base class for tenant-scoped entities.
    All tenant data must include tenant_id for data isolation.
    """

    tenant_id: UUID


class TenantAggregateRoot(AggregateRoot[TId]):
    """
    Base class for tenant-scoped aggregate roots.
    """

    tenant_id: UUID


# Common Value Objects


class PhoneNumber(ValueObject):
    """
    Phone number value object with Iranian phone number support.
    Normalizes and validates phone numbers.
    """

    number: str
    country_code: str = "98"  # Iran default

    @classmethod
    def from_string(cls, phone: str) -> "PhoneNumber":
        """
        Create PhoneNumber from string, normalizing the format.
        Handles various Iranian phone formats.
        """
        # Remove all non-digit characters
        cleaned = "".join(filter(str.isdigit, phone))

        # Handle different formats
        if cleaned.startswith("98") and len(cleaned) == 12:
            # +98XXXXXXXXXX format
            return cls(number=cleaned[2:], country_code="98")
        elif cleaned.startswith("0") and len(cleaned) == 11:
            # 0XXXXXXXXXX format
            return cls(number=cleaned[1:], country_code="98")
        elif len(cleaned) == 10:
            # XXXXXXXXXX format (without leading 0)
            return cls(number=cleaned, country_code="98")
        else:
            # Return as-is if format is unknown
            return cls(number=cleaned, country_code="98")

    @property
    def full_number(self) -> str:
        """Get full international format."""
        return f"+{self.country_code}{self.number}"

    @property
    def local_format(self) -> str:
        """Get local format with leading zero."""
        return f"0{self.number}"

    @property
    def normalized(self) -> str:
        """Get normalized 10-digit format."""
        return self.number

    def __str__(self) -> str:
        return self.full_number


class Money(ValueObject):
    """
    Money value object for handling currency amounts.
    Default currency is IRR (Iranian Rial).
    """

    amount: int  # Store in smallest unit (Rial)
    currency: str = "IRR"

    @property
    def in_toman(self) -> float:
        """Convert Rial to Toman."""
        return self.amount / 10

    @classmethod
    def from_toman(cls, toman: float, currency: str = "IRR") -> "Money":
        """Create Money from Toman amount."""
        return cls(amount=int(toman * 10), currency=currency)

    def __str__(self) -> str:
        return f"{self.amount:,} {self.currency}"


class DateRange(ValueObject):
    """
    Date range value object for time-based queries.
    """

    start_date: datetime
    end_date: datetime

    def contains(self, date: datetime) -> bool:
        """Check if a date falls within the range."""
        return self.start_date <= date <= self.end_date

    @property
    def days(self) -> int:
        """Get number of days in range."""
        return (self.end_date - self.start_date).days


class Percentage(ValueObject):
    """
    Percentage value object.
    Stores as decimal (0.0 - 1.0) internally.
    """

    value: float  # 0.0 to 1.0

    @classmethod
    def from_percent(cls, percent: float) -> "Percentage":
        """Create from percentage value (0-100)."""
        return cls(value=percent / 100)

    @property
    def as_percent(self) -> float:
        """Get as percentage (0-100)."""
        return self.value * 100

    def __str__(self) -> str:
        return f"{self.as_percent:.2f}%"

