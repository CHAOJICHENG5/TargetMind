"""Login / logout / current-account endpoints under /api/v1/auth."""

import os

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from targetmind.server.accounts.account_models import AccountInfo, ProfileUpdate
from targetmind.server.accounts.account_service import (
    SESSION_COOKIE,
    SESSION_TTL,
    AccountError,
    AccountService,
    to_info,
)
from targetmind.server.accounts.account_user_auth import account_from_request
from agent_core import depends_db_session

router = APIRouter(prefix='/auth', tags=['Auth'])
db_session_dependency = depends_db_session()


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _cookie_secure(request: Request) -> bool:
    forced = os.getenv('TM_COOKIE_SECURE')
    if forced is not None:
        return forced.lower() in ('true', '1')
    proto = request.headers.get('x-forwarded-proto', request.url.scheme)
    return proto == 'https'


def _set_session_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        samesite='lax',
        secure=_cookie_secure(request),
        path='/',
    )


@router.post('/login')
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db_session=db_session_dependency,
) -> AccountInfo:
    try:
        token, account = await AccountService(db_session).login(
            body.email, body.password, request.headers.get('user-agent')
        )
    except AccountError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))
    _set_session_cookie(request, response, token)
    return to_info(account)


@router.post('/logout')
async def logout(
    request: Request, response: Response, db_session=db_session_dependency
) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await AccountService(db_session).logout(token)
    response.delete_cookie(SESSION_COOKIE, path='/')
    return {'ok': True}


@router.get('/me')
async def me(request: Request) -> AccountInfo:
    account = await account_from_request(request)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Login required')
    return to_info(account)


@router.post('/change-password')
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    db_session=db_session_dependency,
) -> AccountInfo:
    cached = await account_from_request(request)
    if cached is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Login required')
    service = AccountService(db_session)
    # Re-load in this session so the update is tracked.
    account = await service.get_by_email(cached.email)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Login required')
    try:
        token = await service.change_password(
            account,
            body.current_password,
            body.new_password,
            request.headers.get('user-agent'),
        )
    except AccountError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    _set_session_cookie(request, response, token)
    return to_info(account)


@router.patch('/profile')
async def update_profile(
    body: ProfileUpdate,
    request: Request,
    db_session=db_session_dependency,
) -> AccountInfo:
    """Edit the logged-in account's profile (name, organization, role, field)."""
    cached = await account_from_request(request)
    if cached is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Login required')
    service = AccountService(db_session)
    account = await service.get_by_email(cached.email)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, 'Login required')
    await service.update_profile(account, body)
    return to_info(account)
