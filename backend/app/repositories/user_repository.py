from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def create(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    role: str = "customer",
    dealership_id: int | None = None,
    must_change_password: bool = False,
    commit: bool = True,
) -> User:
    user = User(
        name=name,
        email=email,
        password=password,
        role=role,
        dealership_id=dealership_id,
        must_change_password=must_change_password,
    )
    db.add(user)
    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user