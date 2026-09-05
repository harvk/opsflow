from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import (
    get_authentication_service,
    CurrentUser,
)
from app.domain.user import User
from app.schemas.auth import TokenResponse
from app.schemas.user import UserRead
from app.services.authentication_service import (
    AuthenticationError,
    AuthenticationService,
)


router = APIRouter()


@router.post(
    "/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login_for_access_token(
    form_data: Annotated[
        OAuth2PasswordRequestForm,
        Depends(),
    ],
    authentication_service: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> TokenResponse:
    try:
        user = authentication_service.authenticate(
            email=form_data.username,
            password=form_data.password,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        ) from exc

    access_token = (
        authentication_service.issue_access_token(
            user
        )
    )

    return TokenResponse(
        access_token=access_token,
    )


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
)
def read_current_user(
    current_user: CurrentUser,
) -> UserRead:
    return UserRead.model_validate(
        current_user
    )