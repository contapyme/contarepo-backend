"""
Cliente HTTP hacia contabanc-backend — bank_accounts vive en su propia BD
desde la separación del dominio Banca. contarepo antes leía la tabla directo
por compartir la misma BD física con contapyme.
"""
import uuid
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

from app.config import settings


@dataclass
class BankAccountView:
    id: uuid.UUID
    bank_name: str
    account_number: str
    currency: str
    account_id: uuid.UUID


async def get_bank_accounts_for_company(company_id: uuid.UUID) -> list[BankAccountView]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{settings.CONTABANC_URL}/api/v1/internal/bank-accounts/for-company/{company_id}",
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="No se pudo conectar con contabanc")
    resp.raise_for_status()
    return [
        BankAccountView(
            id=uuid.UUID(a["id"]),
            bank_name=a["bank_name"],
            account_number=a["account_number"],
            currency=a["currency"],
            account_id=uuid.UUID(a["account_id"]),
        )
        for a in resp.json()
    ]
