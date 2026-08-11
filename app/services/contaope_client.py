"""
Cliente HTTP hacia contaope-backend — ope_vouchers vive en su propia BD
desde la separación del dominio (ver contaope-backend#31/#32). contarepo
antes leía la tabla directo por compartir la misma BD física con
contapyme; encontrado por rename test al hacer el flip.
"""
import uuid

import httpx
from fastapi import HTTPException

from app.config import settings


async def get_voucher_ids_by_journal_entries(entry_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    """Mapa journal_entry_id -> voucher_id para un set de asientos."""
    if not entry_ids:
        return {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{settings.CONTAOPE_URL}/api/v1/internal/vouchers/by-journal-entries",
                params={"ids": [str(i) for i in entry_ids]},
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="No se pudo conectar con ContaOPE")
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Error de ContaOPE: {resp.text[:300]}")
    return {uuid.UUID(row["journal_entry_id"]): uuid.UUID(row["voucher_id"]) for row in resp.json()}
