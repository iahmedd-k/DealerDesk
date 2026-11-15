from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import bearer_scheme, get_current_user
from app.models.user import User
from app.repositories import user_repository
from app.schemas.auth import LoginRequest, SignUpRequest, TokenResponse
from app.schemas.user import UserResponse
from app.schemas.workspace import ChangePasswordRequest
from app.services import auth_service


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
def signup(payload: SignUpRequest, db: Session = Depends(get_db)) -> User:
    email = str(payload.email).lower()
    if user_repository.get_by_email(db, email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return user_repository.create(
        db,
        name=payload.name,
        email=email,
        password=auth_service.hash_password(payload.password),
        role="customer",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    description=(
        "Authenticates a user with email and password. "
        "Use the returned bearer token for protected endpoints."
    ),
    response_description="A bearer access token.",
    responses={
        401: {"description": "The email or password is invalid."},
        503: {"description": "Authentication is not configured on the server."},
        422: {"description": "The login request failed validation."},
    },
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = user_repository.get_by_email(db, str(payload.email).lower())
    if user is None or not auth_service.verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        access_token = auth_service.create_access_token(user.id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return TokenResponse(access_token=access_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
    description="Revokes the current bearer token.",
    response_description="The token was revoked successfully.",
    responses={
        401: {"description": "A valid bearer token was not provided."},
    },
)
def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> None:
    auth_service.revoke_token(credentials.credentials)


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


@router.post("/change-password", response_model=UserResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if not auth_service.verify_password(payload.current_password, current_user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password must be different")
    current_user.password = auth_service.hash_password(payload.new_password)
    current_user.must_change_password = False
    db.commit()
    db.refresh(current_user)
    return current_user