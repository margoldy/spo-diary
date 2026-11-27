from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import Schema


class RequestCode(Schema):
    email: Annotated[EmailStr, Field(max_length=254)]

    @field_validator("email")
    @classmethod
    def normalize(cls, value):
        return str(value).lower()


class VerifyCode(Schema):
    code_id: UUID
    code: str = Field(pattern=r"^[0-9]{6}$", min_length=6, max_length=6)


class CodeResponse(Schema):
    code_id: UUID
    expires_at: datetime
    resend_after: int


class UserUpdate(Schema):
    name: str = Field(min_length=1, max_length=80)


class UserResponse(UserUpdate):
    id: UUID
    email: str


class LoginResponse(Schema):
    user: UserResponse
    is_new_user: bool
