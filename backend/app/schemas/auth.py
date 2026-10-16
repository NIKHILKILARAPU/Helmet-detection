"""
Authentication Request and Response Schemas.
"""

from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Staff officer authentication payload."""
    email: str = Field(..., description="Official government officer email")
    password: str = Field(..., min_length=6, description="Plaintext password for verification")


class UserSummary(BaseModel):
    """Safe user profile projection excluding sensitive password hashes."""
    id: str
    employeeId: str
    name: str
    email: str
    role: str
    department: Optional[str] = None
    rank: Optional[str] = None
    status: str


class TokenResponse(BaseModel):
    """Bearer token payload returned upon successful authentication."""
    accessToken: str
    tokenType: str = "bearer"
    expiresInMinutes: int
    user: UserSummary
