import re

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from targetmind.server.accounts.account_user_auth import account_from_request
from targetmind.server.settings.platform_settings import is_platform_locked

# API paths reachable without a login cookie. Sandbox callbacks (webhooks,
# sandbox settings, the NCBI relay) authenticate with X-Session-API-Key inside
# their own handlers.
_PUBLIC_API = re.compile(
    r'^/api/v1/('
    r'auth/(login|logout)'
    r'|web-client/config'
    r'|webhooks/.*'
    r'|sandboxes/[^/]+/settings(/.*)?'
    r'|ncbi/eutils/[a-z]+\.fcgi'
    r')$'
)
# Reachable while the account still has to replace its issued password.
_PASSWORD_CHANGE_API = re.compile(r'^/api/v1/auth/.*$')


class AccountAuthMiddleware(BaseHTTPMiddleware):
    """Require a valid TargetMind login for every /api route (defence in depth;
    data services additionally scope everything by the account's user id)."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if (
            request.method == 'OPTIONS'
            or not path.startswith('/api/')
            or _PUBLIC_API.match(path)
        ):
            return await call_next(request)

        account = await account_from_request(request)
        if account is None:
            return JSONResponse({'detail': 'Login required'}, status_code=401)
        if account.must_change_password and not _PASSWORD_CHANGE_API.match(path):
            return JSONResponse({'detail': 'password_change_required'}, status_code=403)
        if is_platform_locked(request.method, path):
            # Platform configuration is edited on the host, not through the
            # API — for admins too.
            return JSONResponse({'detail': 'platform_managed'}, status_code=403)
        return await call_next(request)
