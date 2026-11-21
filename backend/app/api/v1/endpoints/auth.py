from fastapi import APIRouter, Depends, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.roles import DEALERSHIP_ADMIN_ROLE
from app.db.session import get_db
from app.dependencies.auth import bearer_scheme, get_current_user
from app.dependencies.workspace import require_roles
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    SignUpRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse, UserUpdateRequest
from app.schemas.workspace import ActivationRequest, ChangePasswordRequest
from app.services import account_service


router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address, default_limits=[])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user account",
    description="Registers a new user account using a name, email address, and password.",
    response_description="The newly created user account.",
    responses={
        409: {"description": "An account with this email already exists."},
        422: {"description": "The request data failed validation."},
    },
)
@limiter.limit("10/minute")
def signup(
    request: Request,
    payload: SignUpRequest,
    db: Session = Depends(get_db),
) -> User:
    return account_service.signup(db, payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    description=(
        "Authenticates a user with email and password. "
        "Use the access token for protected endpoints and rotate the refresh token when it expires."
    ),
    response_description="A bearer access token.",
    responses={
        401: {"description": "The email or password is invalid."},
        503: {"description": "Authentication is not configured on the server."},
        422: {"description": "The login request failed validation."},
    },
)
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return account_service.login(db, payload)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
    description="Revokes the current access token and all refresh tokens for the account.",
    response_description="The token was revoked successfully.",
    responses={
        401: {"description": "A valid bearer token was not provided."},
    },
)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    account_service.logout(db, credentials.credentials, current_user)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current user",
    description="Returns the profile associated with the current bearer token.",
    response_description="The authenticated user's profile.",
    responses={
        401: {"description": "The token is invalid, expired, or revoked."},
    },
)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    current_user: User = Depends(require_roles(DEALERSHIP_ADMIN_ROLE)),
    db: Session = Depends(get_db),
) -> list[User]:
    return account_service.list_users(db, current_user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return account_service.update_current_user(db, current_user, payload)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    account_service.delete_current_user(db, current_user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token",
    description="Issues a new access token and refresh token, revoking the refresh token provided.",
)
@limiter.limit("10/minute")
def refresh_access_token(
    request: Request,
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return account_service.refresh_access_token(db, payload)


@router.post("/request-password-reset")
@limiter.limit("5/minute")
def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return account_service.request_password_reset(db, payload)


@router.post("/reset-password")
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return account_service.reset_password(db, payload)


@router.post("/activate-invitation", response_model=UserResponse)
def activate_invitation(
    payload: ActivationRequest,
    db: Session = Depends(get_db),
) -> User:
    return account_service.activate_invitation(db, payload)


@router.post("/change-password", response_model=UserResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return account_service.change_password(db, current_user, payload)
