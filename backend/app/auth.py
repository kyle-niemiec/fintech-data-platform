from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

_ALGORITHM = "HS256"
_TOKEN_EXPIRY_HOURS = 8

"""
Set up the bearer token URL
"""
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

"""
Sign and return a JWT containing the caller's subject and role.
"""
def create_token(subject: str, role: str) -> str:
    payload = {
        "sub": subject,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_TOKEN_EXPIRY_HOURS),
    }

    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)

"""
Decode and validate the bearer token. Raises 401 on any failure.
"""
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

"""
Requires the caller to hold the operator role.
"""
def require_operator(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "operator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )

    return user

"""
Requires the caller to hold the operator or observer role.
"""
def require_observer(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in {"operator", "observer"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Observer role or higher required",
        )

    return user
