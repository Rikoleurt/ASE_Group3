from fastapi import APIRouter, HTTPException, status

from backend.app.data.user_data_controller import UserDataController
from backend.app.model.user import LoginResponse, UserCreate, UserLogin, UserPublic


router = APIRouter(prefix="/users", tags=["users"])
user_data_controller = UserDataController()


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: UserCreate) -> UserPublic:
    user = user_data_controller.create_user(
        email=str(payload.email),
        password=payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    return UserPublic(id=user.id, email=user.email)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
def login(payload: UserLogin) -> LoginResponse:
    user = user_data_controller.authenticate(
        email=str(payload.email),
        password=payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return LoginResponse(
        authenticated=True,
        user=UserPublic(id=user.id, email=user.email),
    )
