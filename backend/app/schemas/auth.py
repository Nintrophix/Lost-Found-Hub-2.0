"""Request and response contracts for authentication and user management."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.db.enums import AccountStatus, UserRole

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("Password cannot be only whitespace.")
    return value


NewPassword = Annotated[
    str,
    StringConstraints(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH),
    AfterValidator(_not_blank),
]
AnyPassword = Annotated[str, StringConstraints(min_length=1, max_length=PASSWORD_MAX_LENGTH)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
OpaqueToken = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(StrictModel):
    name: PersonName
    email: EmailStr
    password: NewPassword


class LoginRequest(StrictModel):
    email: EmailStr
    password: AnyPassword


class EmailRequest(StrictModel):
    email: EmailStr


class TokenRequest(StrictModel):
    token: OpaqueToken


class ResetPasswordRequest(StrictModel):
    token: OpaqueToken
    new_password: NewPassword


class ChangePasswordRequest(StrictModel):
    current_password: AnyPassword
    new_password: NewPassword


class UserUpdateRequest(StrictModel):
    role: UserRole | None = None
    account_status: AccountStatus | None = None


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: UserRole
    email_verified: bool = Field(validation_alias="is_email_verified")
    account_status: AccountStatus
    created_at: datetime
