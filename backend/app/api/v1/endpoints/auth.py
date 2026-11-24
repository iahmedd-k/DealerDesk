from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.roles import DEALERSHIP_ADMIN_ROLE
from app.core.limiter import limiter
from app.db.session import get_db
from app.dependencies.auth import bearer_scheme, get_current_user
from app.dependencies.workspace import require_roles
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    ResendVerificationRequest,
    SignUpRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.user import UserResponse, UserUpdateRequest
from app.schemas.workspace import ActivationRequest, ChangePasswordRequest
from app.services import account_service


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    is_prod = getattr(settings, "environment", "development").lower() == "production"
    response.set_cookie(
        key="dd_access",
        value=access_token,
        max_age=1800,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        path="/",
    )
    response.set_cookie(
        key="dd_refresh",
        value=refresh_token,
        max_age=2592000,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="dd_access", path="/")
    response.delete_cookie(key="dd_refresh", path="/api/v1/auth")


router = APIRouter(prefix="/auth", tags=["Authentication"])


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
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    tokens = account_service.login(db, payload)
    _set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


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
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    token = (
        credentials.credentials
        if credentials is not None and credentials.credentials
        else request.cookies.get("dd_access")
    )
    if token:
        account_service.logout(db, token, current_user)
    _clear_auth_cookies(response)


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
    response: Response,
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    refresh_token = payload.refresh_token or request.cookies.get("dd_refresh")
    if not refresh_token:
        raise UnauthorizedError("Refresh token required")
    tokens = account_service.refresh_access_token(
        db, RefreshTokenRequest(refresh_token=refresh_token)
    )
    _set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens


@router.post(
    "/verify-email",
    summary="Verify email address",
    description="Validates an email verification token and marks the user's email as verified.",
)
@limiter.limit("5/minute")
def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return account_service.verify_email(db, payload.token)


@router.post(
    "/resend-verification",
    summary="Resend verification email",
    description="Generates a new email verification token and sends it if the user has an unverified account.",
)
@limiter.limit("3/minute")
def resend_verification(
    request: Request,
    payload: ResendVerificationRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return account_service.resend_verification_email(db, str(payload.email))


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
