from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import create_token
from app.config import settings
from app.schemas.auth import TokenResponse

router = APIRouter(tags=["auth"])

"""
Issue a JWT for a valid username/password pair.

Credentials are statically configured via environment variables.
Usernames: "operator" (read/write), "observer" (read-only).
"""
@router.post(
    "/token",
    response_model=TokenResponse
)
def login(form: OAuth2PasswordRequestForm = Depends()):
    if form.username == "operator" and form.password == settings.operator_password:
        role = "operator"
    elif form.username == "observer" and form.password == settings.observer_password:
        role = "observer"
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_token(subject=form.username, role=role))
