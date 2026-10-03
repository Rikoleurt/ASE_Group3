from pydantic import BaseModel, EmailStr


class User(BaseModel):
    """Internal representation matching the SQL user table."""

    id: int
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    email: EmailStr


class LoginResponse(BaseModel):
    authenticated: bool
    user: UserPublic
