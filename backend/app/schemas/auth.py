"""Request and response contracts for authentication and user management."""

import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, StringConstraints

from app.db.enums import AccountStatus, UserRole

PASSWORD_MIN_LENGTH = 8
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


def _normalise_campus_id(value: object) -> object:
    return re.sub(r"\s+", "", value).upper() if isinstance(value, str) else value


def _normalise_phone(value: object) -> object:
    if not isinstance(value, str):
        return value
    cleaned = re.sub(r"[\s\-().]", "", value)
    return cleaned or None


# SRM register number (for example RA2111003010123) or employee ID.
CampusId = Annotated[
    str,
    BeforeValidator(_normalise_campus_id),
    StringConstraints(pattern=r"^[A-Z0-9]{5,20}$"),
]
Department = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Phone = Annotated[
    Annotated[str, StringConstraints(pattern=r"^\+?[0-9]{7,15}$")] | None,
    BeforeValidator(_normalise_phone),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(StrictModel):
    name: PersonName
    email: EmailStr
    password: NewPassword
    campus_id: CampusId
    department: Department
    phone: Phone = None


class ProfileUpdate(StrictModel):
    """Fields a user may change about themselves. Email and SRM ID are fixed after sign-up."""

    name: PersonName | None = None
    department: Department | None = None
    phone: Phone = None


class LoginRequest(StrictModel):
    email: EmailStr
    password: AnyPassword


class EmailRequest(StrictModel):
    email: EmailStr


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
    account_status: AccountStatus
    campus_id: str | None
    department: str | None
    phone: str | None
    created_at: datetime


class SessionResponse(BaseModel):
    user: UserResponse | None
    allowed_email_domains: list[str]
