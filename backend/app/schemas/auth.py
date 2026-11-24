from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
        description="The user's display name.",
        examples=["Ahmed Khan"],
    )
    email: EmailStr = Field(
        description="A unique email address used for login.",
        examples=["ahmed@example.com"],
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="The account password. Must contain at least 8 characters.",
        examples=["strong-password-123"],
    )


class LoginRequest(BaseModel):
    email: EmailStr = Field(
        description="The email address used during registration.",
        examples=["ahmed@example.com"],
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="The account password.",
        examples=["strong-password-123"],
    )


class TokenResponse(BaseModel):
    access_token: str = Field(description="JWT access token.")
    token_type: str = Field(
        default="bearer", description="Token authentication scheme."
    )
    refresh_token: str = Field(description="Single-use refresh token.")


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=32, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
