from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from agent_core import utc_now
from agent_core import Base


class StoredAccount(Base):
    __tablename__ = 'accounts'

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    organization: Mapped[str | None] = mapped_column(String, nullable=True)
    # Profile fields from the access application (website /apply).
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    research_field: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str] = mapped_column(String)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class StoredAccountSession(Base):
    __tablename__ = 'account_sessions'

    # sha256 of the cookie token; the raw token is never stored.
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String, ForeignKey('accounts.id', ondelete='CASCADE'), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)


class AccountInfo(BaseModel):
    """Public view of an account (no secrets)."""

    id: str
    email: str
    name: str | None = None
    organization: str | None = None
    role: str | None = None
    research_field: str | None = None
    is_admin: bool = False
    must_change_password: bool = False


# Same choices as the access application on the website (/apply).
ACCOUNT_ROLES: tuple[str, ...] = (
    'student',
    'researcher',
    'pi',
    'industry',
    'clinician',
    'other',
)


class ProfileUpdate(BaseModel):
    """Fields an account may edit on its profile page (email is the login)."""

    name: str | None = Field(default=None, max_length=100)
    organization: str | None = Field(default=None, max_length=200)
    role: str | None = None
    research_field: str | None = Field(default=None, max_length=200)

    @field_validator('name', 'organization', 'research_field', 'role', mode='before')
    @classmethod
    def _blank_is_none(cls, value):
        if isinstance(value, str):
            value = ' '.join(value.split())
            return value or None
        return value

    @field_validator('role')
    @classmethod
    def _known_role(cls, value):
        if value is not None and value not in ACCOUNT_ROLES:
            raise ValueError(f'role must be one of {", ".join(ACCOUNT_ROLES)}')
        return value
