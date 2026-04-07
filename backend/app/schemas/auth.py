from pydantic import BaseModel

"""
Response schema for a successfully issued token.
"""
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
