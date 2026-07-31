"""Local bearer-token authentication (TDD §29). Trust boundary is "same
machine, same local user" — deliberately not OAuth/session complexity,
which would be solving the (deferred) cloud phase's problem prematurely.
"""

from __future__ import annotations

import secrets
from pathlib import Path


class AuthTokenManager:
    def __init__(self, token_path: Path | str) -> None:
        self._token_path = Path(token_path)

    def generate_and_persist(self) -> str:
        """A fresh, high-entropy token every Core start — rotates on
        restart, so a stale Adapter session can't replay old requests.
        """
        token = secrets.token_urlsafe(32)
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(token)
        try:
            self._token_path.chmod(0o600)  # restrict to current user, best-effort on the platform
        except OSError:
            pass
        return token


def extract_bearer_token(authorization_header: str | None) -> str | None:
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return None
    return authorization_header.removeprefix("Bearer ").strip() or None
