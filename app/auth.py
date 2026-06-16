from typing import Optional

from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import ADMIN_SECRET
from app.store import validate_api_key

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(x_api_key: Optional[str] = Security(api_key_header)) -> dict:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    key_info = validate_api_key(x_api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    return key_info


async def require_admin(x_admin_secret: Optional[str] = Header(None, alias="X-Admin-Secret")) -> None:
    if not x_admin_secret or x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
