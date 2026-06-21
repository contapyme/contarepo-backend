"""
Setup de BD para CI: crea tablas, usuario admin y emite un JWT.
Solo para entornos de CI — no ejecutar en producción.

Uso: python ci_seed.py
Requiere: DATABASE_URL en el entorno y keys/private.pem generada antes de correr.
Imprime TOKEN=<jwt> al final para que el reusable workflow lo capture (auth_type: seed).
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt as _bcrypt
from jose import jwt
from sqlalchemy import text

from app.config import settings
from app.db.base import Base
from app.db.session import engine

# Registrar todos los modelos en Base.metadata antes de create_all
import app.models.user           # noqa: F401 — User, UserCompany
import app.models.company        # noqa: F401 — Company
import app.models.account        # noqa: F401
import app.models.balance_cache  # noqa: F401
import app.models.bank_account   # noqa: F401
import app.models.contact        # noqa: F401
import app.models.cost_center    # noqa: F401
import app.models.fiscal_period  # noqa: F401
import app.models.journal_entry  # noqa: F401
import app.models.operation_form     # noqa: F401
import app.models.operation_template  # noqa: F401

ADMIN_EMAIL = "admin@contapyme.pe"
ADMIN_PASSWORD = "Admin2024"
ADMIN_NAME = "Admin CI"


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _generate_token(user_id: str) -> str:
    private_key = Path("keys/private.pem").read_text()
    expire = datetime.now(timezone.utc) + timedelta(hours=2)
    return jwt.encode({"sub": user_id, "exp": expire}, private_key, algorithm=settings.ALGORITHM)


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Tablas creadas.")

        row = await conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": ADMIN_EMAIL},
        )
        existing = row.fetchone()
        if existing:
            user_id = str(existing[0])
            print(f"Usuario ya existe: {ADMIN_EMAIL}")
        else:
            user_id = str(uuid.uuid4())
            await conn.execute(
                text("""
                    INSERT INTO users (id, email, hashed_password, full_name, is_active, is_superadmin)
                    VALUES (:id, :email, :pwd, :name, true, true)
                """),
                {
                    "id": user_id,
                    "email": ADMIN_EMAIL,
                    "pwd": _hash_password(ADMIN_PASSWORD),
                    "name": ADMIN_NAME,
                },
            )
            print(f"Usuario admin creado: {ADMIN_EMAIL}")

    token = _generate_token(user_id)
    print(f"TOKEN={token}")


asyncio.run(main())
