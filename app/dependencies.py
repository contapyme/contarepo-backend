"""
Resolución de usuario/empresa vía contasist-backend, dueño de
users/user_companies/user_app_access. Este servicio no lee esas tablas
localmente — decodifica el JWT (misma llave pública en todo el stack, no
hace falta red para eso) y resuelve el acceso a la empresa por HTTP, mismo
patrón que ya usa contabanc-backend/app/dependencies.py contra contapyme-backend.
"""
import uuid
import httpx
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from app.config import settings
from app.core.security import decode_token

bearer = HTTPBearer()


class CurrentUser:
    def __init__(self, id: uuid.UUID):
        self.id = id


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> CurrentUser:
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    return CurrentUser(id=uuid.UUID(user_id))


class CompanyContext:
    def __init__(self, company_id: uuid.UUID, role: str):
        self.company_id = company_id
        self.role = role

    def require_role(self, *roles: str):
        if self.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")


async def get_active_company(
    x_company_id: str = Header(..., alias="X-Company-ID"),
    current_user: CurrentUser = Depends(get_current_user),
) -> CompanyContext:
    try:
        cid = uuid.UUID(x_company_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Company-ID inválido")

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(
                f"{settings.CONTASIST_URL}/api/v1/internal/user-access",
                params={"user_id": str(current_user.id), "company_id": str(cid)},
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo validar el acceso (contasist no disponible)",
            )

    if resp.status_code == 403:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta empresa")
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Error validando acceso")

    data = resp.json()
    return CompanyContext(company_id=cid, role=data["role"])
