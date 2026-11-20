from enum import Enum
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Role(str, Enum):
    player = "player"
    organiser = "organiser"
    administrator = "administrator"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128, repr=False)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        if not isinstance(value, str):
            return value
        value = value.strip().casefold()
        if not re.fullmatch(r"[a-z0-9_.-]{3,64}", value):
            raise ValueError("Use 3–64 letters, digits, dots, underscores or hyphens")
        return value


class RegisterRequest(LoginRequest):
    password: str = Field(min_length=15, max_length=128, repr=False)
    create_player: bool = True
    player_name: str | None = Field(default=None, min_length=1, max_length=100)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: Role
    player_id: int | None
    is_active: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 300
    user: UserOut


class RoleChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role


class OrganiserAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int


class LinkPlayerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: int
    reason: str = Field(min_length=10, max_length=200)
