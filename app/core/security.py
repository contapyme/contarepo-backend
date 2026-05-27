from pathlib import Path
from jose import jwt
from app.config import settings

_public_key: str | None = None


def _get_public_key() -> str:
    global _public_key
    if _public_key is None:
        if settings.RSA_PUBLIC_KEY:
            _public_key = settings.RSA_PUBLIC_KEY.replace("\\n", "\n")
        else:
            path = Path(settings.PUBLIC_KEY_PATH)
            if not path.exists():
                raise RuntimeError(
                    "Llave pública RSA no encontrada. "
                    "En producción: configura RSA_PUBLIC_KEY en las variables de entorno. "
                    "En desarrollo: genera las llaves con: openssl genrsa -out keys/private.pem 2048 && "
                    "openssl rsa -in keys/private.pem -pubout -out keys/public.pem"
                )
            _public_key = path.read_text()
    return _public_key


def decode_token(token: str) -> dict:
    return jwt.decode(token, _get_public_key(), algorithms=[settings.ALGORITHM])
