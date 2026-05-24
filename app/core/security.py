from pathlib import Path
from jose import jwt
from app.config import settings

_public_key: str | None = None


def _get_public_key() -> str:
    global _public_key
    if _public_key is None:
        _public_key = Path(settings.PUBLIC_KEY_PATH).read_text()
    return _public_key


def decode_token(token: str) -> dict:
    return jwt.decode(token, _get_public_key(), algorithms=[settings.ALGORITHM])
