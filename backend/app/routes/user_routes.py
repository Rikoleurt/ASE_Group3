from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from backend.app.data_controller.user_data_controller import UserDataController
from backend.app.model.user import LoginResponse, UserCreate, UserEmail, UserLogin, UserPublic, UserUsername


router = APIRouter(prefix="/users", tags=["users"])



def get_user_data_controller() -> UserDataController:
    return UserDataController()

UserController = Annotated[UserDataController, Depends(get_user_data_controller)]

@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: UserCreate, user_data_controller: UserController) -> UserPublic:
    user = user_data_controller.create_user(
        email=str(payload.email),
        username=str(payload.username),
        password=payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    return UserPublic(id=user.id, email=user.email, username=user.username)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
def login(payload: UserLogin, user_data_controller: UserController) -> LoginResponse:
    user = user_data_controller.authenticate(
        email=str(payload.email),
        username=payload.username,
        password=payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return LoginResponse(
        authenticated=True,
        user=UserPublic(id=user.id, email=user.email, username=user.username),
    )


@router.get("/{user_id}/email", response_model=UserEmail)
def get_email(user_id: Annotated[int, Path(gt=0)], user_data_controller: UserController) -> UserEmail:
    email = user_data_controller.get_email_by_id(user_id)
    if email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserEmail(email=email)


@router.get("/{user_id}/username", response_model=UserUsername)
def get_username(user_id: Annotated[int, Path(gt=0)], user_data_controller: UserController) -> UserUsername:
    username = user_data_controller.get_username_by_id(user_id)
    if username is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserUsername(username=username)
