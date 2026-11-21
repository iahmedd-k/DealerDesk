from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    id: int = Field(description="Unique user identifier.")
    name: str = Field(description="User's display name.")
    email: EmailStr = Field(description="User's email address.")
    role: str = Field(description="User's application role.")
    dealership_id: int | None = Field(default=None)
    is_active: bool = Field(default=True)
    must_change_password: bool = Field(default=False)

    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
