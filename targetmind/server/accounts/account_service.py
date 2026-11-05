"""Account and session operations shared by the auth router, the request
authenticator and the admin CLI."""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core import utc_now
from targetmind.server.accounts.account_models import (
    AccountInfo,
    ProfileUpdate,
    StoredAccount,
    StoredAccountSession,
)
from targetmind.server.accounts.passwords import (
    hash_password,
    password_problem,
    verify_password,
)

SESSION_COOKIE = 'tm_session'
SESSION_TTL = timedelta(days=int(os.getenv('TM_SESSION_DAYS', '7')))
MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)

# Verified against when the email is unknown so response time does not reveal
# whether an account exists.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


class AccountError(Exception):
    """User-facing account failure (bad credentials, locked, weak password)."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def to_info(account: StoredAccount) -> AccountInfo:
    return AccountInfo(
        id=account.id,
        email=account.email,
        name=account.name,
        organization=account.organization,
        role=account.role,
        research_field=account.research_field,
        is_admin=account.is_admin,
        must_change_password=account.must_change_password,
    )


def _aware(value: datetime | None) -> datetime | None:
    # SQLite drops tzinfo; values are always written as UTC.
    if value is not None and value.tzinfo is None:
        from datetime import UTC

        return value.replace(tzinfo=UTC)
    return value


@dataclass
class AccountService:
    db_session: AsyncSession

    async def get_by_email(self, email: str) -> StoredAccount | None:
        return await self.db_session.scalar(
            select(StoredAccount).where(StoredAccount.email == normalize_email(email))
        )

    async def get_by_session_token(self, token: str) -> StoredAccount | None:
        row = await self.db_session.execute(
            select(StoredAccount, StoredAccountSession)
            .join(StoredAccountSession)
            .where(StoredAccountSession.token_hash == hash_token(token))
        )
        found = row.first()
        if found is None:
            return None
        account, session = found
        expires_at = _aware(session.expires_at)
        if not account.is_active or (expires_at and expires_at < utc_now()):
            return None
        return account

    async def login(
        self, email: str, password: str, user_agent: str | None = None
    ) -> tuple[str, StoredAccount]:
        account = await self.get_by_email(email)
        if account is None:
            verify_password(password, _DUMMY_HASH)
            raise AccountError('Incorrect email or password')
        locked_until = _aware(account.locked_until)
        if locked_until and locked_until > utc_now():
            raise AccountError('Too many failed attempts, try again in 15 minutes')
        if not verify_password(password, account.password_hash):
            account.failed_logins = (account.failed_logins or 0) + 1
            if account.failed_logins >= MAX_FAILED_LOGINS:
                account.locked_until = utc_now() + LOCKOUT
                account.failed_logins = 0
            await self.db_session.commit()
            raise AccountError('Incorrect email or password')
        if not account.is_active:
            raise AccountError('This account has been disabled')

        account.failed_logins = 0
        account.locked_until = None
        account.last_login_at = utc_now()
        token = await self._new_session(account.id, user_agent)
        await self.db_session.commit()
        return token, account

    async def logout(self, token: str) -> None:
        await self.db_session.execute(
            delete(StoredAccountSession).where(
                StoredAccountSession.token_hash == hash_token(token)
            )
        )
        await self.db_session.commit()

    async def change_password(
        self,
        account: StoredAccount,
        current_password: str,
        new_password: str,
        user_agent: str | None = None,
    ) -> str:
        """Change the password, revoke every session and return a fresh one."""
        if not verify_password(current_password, account.password_hash):
            raise AccountError('Current password is incorrect')
        problem = password_problem(new_password)
        if problem:
            raise AccountError(problem)
        if new_password == current_password:
            raise AccountError('New password must differ from the current one')
        account.password_hash = hash_password(new_password)
        account.must_change_password = False
        await self.db_session.execute(
            delete(StoredAccountSession).where(
                StoredAccountSession.account_id == account.id
            )
        )
        token = await self._new_session(account.id, user_agent)
        await self.db_session.commit()
        return token

    async def update_profile(
        self, account: StoredAccount, update: ProfileUpdate
    ) -> StoredAccount:
        account.name = update.name
        account.organization = update.organization
        account.role = update.role
        account.research_field = update.research_field
        await self.db_session.commit()
        return account

    async def _new_session(self, account_id: str, user_agent: str | None) -> str:
        token = secrets.token_urlsafe(32)
        now = utc_now()
        self.db_session.add(
            StoredAccountSession(
                token_hash=hash_token(token),
                account_id=account_id,
                created_at=now,
                expires_at=now + SESSION_TTL,
                user_agent=(user_agent or '')[:255] or None,
            )
        )
        # Opportunistic cleanup of this account's expired sessions.
        await self.db_session.execute(
            delete(StoredAccountSession).where(
                StoredAccountSession.account_id == account_id,
                StoredAccountSession.expires_at < now,
            )
        )
        return token


def new_account_id() -> str:
    return uuid.uuid4().hex
