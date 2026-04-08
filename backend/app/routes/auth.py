from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_token, verify_password
from app.db import get_auth_db
from app.models.principal import Principal
from app.schemas.auth import TokenResponse

router = APIRouter(tags=["auth"])

"""
Issue a JWT for a valid username/password pair.

Credentials are verified against the principal table (seeded via `make seed-principals`).
"""
@router.post(
    "/token",
    response_model=TokenResponse
)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_auth_db)):
    principal = db.query(Principal).filter(Principal.username == form.username).first()

    if principal is None or not principal.is_active or not verify_password(form.password, principal.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_token(subject=principal.username, role=principal.role))
