from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from targetmind.server.accounts.account_service import (
    SESSION_COOKIE,
    AccountService,
)
from agent_core import DefaultUserAuth
from agent_core import UserAuth

# Set on request.state by AccountAuthMiddleware once the cookie is validated.
REQUEST_ACCOUNT_ATTR = 'tm_account'


async def account_from_request(request: Request):
    """Return the logged-in StoredAccount for this request, or None."""
    account = getattr(request.state, REQUEST_ACCOUNT_ATTR, None)
    if account is not None:
        return account
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    from agent_core import get_global_config

    session_maker = await get_global_config().db_session.get_async_session_maker()
    async with session_maker() as db_session:
        account = await AccountService(db_session).get_by_session_token(token)
    if account is not None:
        setattr(request.state, REQUEST_ACCOUNT_ATTR, account)
    return account


@dataclass
class AccountUserAuth(DefaultUserAuth):
    """UserAuth backed by TargetMind accounts: one user id per account, with
    per-account settings / secrets files and data scoped by that id."""

    user_id: str | None = None
    email: str | None = None

    async def get_user_id(self) -> str | None:
        return self.user_id

    async def get_user_email(self) -> str | None:
        return self.email

    @classmethod
    async def get_instance(cls, request: Request) -> UserAuth:
        account = await account_from_request(request)
        if account is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Login required')
        return AccountUserAuth(user_id=account.id, email=account.email)

    @classmethod
    async def get_for_user(cls, user_id: str) -> UserAuth:
        return AccountUserAuth(user_id=user_id)
