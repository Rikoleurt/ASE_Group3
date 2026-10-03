from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """Internal representation matching the SQL user table."""

    id: int
    email: EmailStr
    password: str = Field(repr=False)


class UserCreate(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=1024, repr=False)


class UserLogin(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=1024, repr=False)


class UserPublic(BaseModel):
    id: int
    email: EmailStr


class LoginResponse(BaseModel):
    authenticated: bool
    user: UserPublic
