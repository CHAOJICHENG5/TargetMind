"""Password hashing with stdlib scrypt (no extra dependency).

Stored format: ``scrypt$<n>$<r>$<p>$<salt b64>$<hash b64>`` so parameters can
be raised later without invalidating existing hashes.
"""

import base64
import hashlib
import hmac
import secrets
import string

_N, _R, _P, _DKLEN = 2**14, 8, 1, 32
MIN_PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN
    )
    b64 = base64.b64encode
    return f'scrypt${_N}${_R}${_P}${b64(salt).decode()}${b64(digest).decode()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split('$')
        if scheme != 'scrypt':
            return False
        expected = base64.b64decode(hash_b64)
        digest = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


def password_problem(password: str) -> str | None:
    """Return a reason the password is unacceptable, or None if it is fine."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f'Password must be at least {MIN_PASSWORD_LENGTH} characters'
    if password.isdigit() or password.isalpha():
        return 'Password must mix letters with digits or symbols'
    return None


def generate_password(length: int = 14) -> str:
    """Random initial password, avoiding look-alike characters."""
    alphabet = ''.join(
        c for c in string.ascii_letters + string.digits if c not in 'Il1O0o'
    )
    while True:
        candidate = ''.join(secrets.choice(alphabet) for _ in range(length))
        if password_problem(candidate) is None:
            return candidate
