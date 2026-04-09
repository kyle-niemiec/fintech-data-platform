import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jwt import PyJWKClient
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidTokenError,
    MissingRequiredClaimError,
    PyJWKClientError,
)

from app.config import settings

_ALGORITHM = "RS256"
_VALID_ROLES = {"operator", "observer", "pipeline"}

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{settings.keycloak_realm_url}/protocol/openid-connect/auth",
    tokenUrl=f"{settings.keycloak_realm_url}/protocol/openid-connect/token",
)

_jwks_client = PyJWKClient(
    f"{settings.keycloak_realm_url}/protocol/openid-connect/certs"
)

"""
Extract the current user role, expecting only one valid role. Only used when extracting the user
info from the ID token.
"""
def _extract_single_api_role(payload: dict) -> str:
    client_roles = (
        payload.get("resource_access", {})
        .get(settings.keycloak_api_client_id, {})
        .get("roles", [])
    )

    if isinstance(client_roles, str):
        client_roles = [client_roles]

    if not isinstance(client_roles, list):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token role claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    matched_roles = sorted({role for role in client_roles if role in _VALID_ROLES})

    if not matched_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No recognized API role",
        )

    if len(matched_roles) > 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token contains multiple API roles",
        )

    return matched_roles[0]

"""
Get the user ID info from the OIDC JWT
"""
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[_ALGORITHM],
            issuer=settings.keycloak_realm_url,
            audience=settings.keycloak_api_audience,
            options={"require": ["exp", "iss", "aud"]},
        )

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except (InvalidIssuerError, InvalidAudienceError, MissingRequiredClaimError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except (InvalidTokenError, PyJWKClientError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = payload.get("preferred_username") or payload.get("sub")

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "sub": subject,
        "role": _extract_single_api_role(payload),
    }

"""
Require that the user has an operator role.
"""
def require_operator(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "operator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )

    return user

"""
Require that the user has an observer or operator role.
"""
def require_observer(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in {"operator", "observer"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Observer role or higher required",
        )

    return user

"""
Require that the user has a pipeline role.
"""
def require_pipeline(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "pipeline":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pipeline role required",
        )

    return user

"""
Require that the user has an operator or pipeline role.
"""
def require_writer(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in {"operator", "pipeline"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or pipeline role required",
        )

    return user
