"""Authentication and user-administration schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import RoleName


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    username: str
    email: str
    role: RoleName
    employee_id: str | None = None
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime | None = None


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9._-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    employee_id: str | None = None


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9._-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: RoleName
    employee_id: str | None = None


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    role: RoleName | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: str
    name: RoleName
    description: str
    permissions: list = []


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)


TokenResponse.model_rebuild()
