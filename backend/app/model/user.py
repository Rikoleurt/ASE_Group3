from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class User(BaseModel):
    """Internal representation matching the SQL user table."""

    id: int
    email: EmailStr
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(repr=False)
    is_admin: bool = False
    is_reviewer: bool = False


class UserCreate(BaseModel):
    email: EmailStr = Field(max_length=255)
    username: str = Field(min_length=1, max_length=255, pattern=r"\S")
    password: str = Field(min_length=1, max_length=1024, repr=False)


class UserLogin(BaseModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, min_length=1, max_length=255, pattern=r"\S")
    password: str = Field(min_length=1, max_length=1024, repr=False)

    @model_validator(mode="after")
    def require_identifier(self):
        if self.email is None and self.username is None:
            raise ValueError("An email or username is required.")
        return self


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr


class Account(UserPublic):
    """The logged-in user with their roles. Serialised as UserPublic wherever a response declares that."""

    is_admin: bool = False
    is_reviewer: bool = False


class DuplicateUserDetail(BaseModel):
    code: Literal["duplicate_user"]
    field: Literal["email", "username"] | None = Field(
        description="The conflicting field, or null if the database constraint is not recognized.",
    )


class RegistrationConflict(BaseModel):
    detail: DuplicateUserDetail


class SessionUser(BaseModel):
    user: UserPublic
    csrf_token: str
    reviewer: bool = False  # may review sign corrections (the reviewer role, or SIGN_REVIEWERS)
    admin: bool = False  # may manage roles on the admin page


class LoginResponse(SessionUser):
    authenticated: bool


class UserEmail(BaseModel):
    email: EmailStr


class UserUsername(BaseModel):
    username: str


class AdminUser(BaseModel):
    """A row on the admin page."""

    id: int
    username: str
    email: EmailStr
    admin: bool
    reviewer: bool
    reviewer_from_env: bool = Field(description="Named in SIGN_REVIEWERS, so a reviewer whatever the role says.")


class AdminUserPage(BaseModel):
    items: list[AdminUser]
    total: int


class RoleUpdate(BaseModel):
    """Roles to set; a missing role is left as it is."""

    admin: bool | None = None
    reviewer: bool | None = None

    @model_validator(mode="after")
    def require_a_role(self):
        if self.admin is None and self.reviewer is None:
            raise ValueError("Give admin, reviewer or both.")
        return self
