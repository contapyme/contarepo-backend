import uuid
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import User, UserCompany

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    uid = uuid.UUID(user_id)
    result = await db.execute(select(User).where(User.id == uid, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user


class CompanyContext:
    def __init__(self, company_id: uuid.UUID, role: str):
        self.company_id = company_id
        self.role = role

    def require_role(self, *roles: str):
        if self.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")


async def get_active_company(
    x_company_id: str = Header(..., alias="X-Company-ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyContext:
    try:
        cid = uuid.UUID(x_company_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Company-ID inválido")

    result = await db.execute(
        select(UserCompany).where(
            UserCompany.user_id == current_user.id,
            UserCompany.company_id == cid,
            UserCompany.is_active == True,
        )
    )
    uc = result.scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta empresa")
    return CompanyContext(company_id=cid, role=uc.role)
