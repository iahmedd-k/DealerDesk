from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace import Vehicle, VehicleImage


def lock_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
) -> Vehicle | None:
    return db.scalar(
        select(Vehicle)
        .where(
            Vehicle.id == vehicle_id,
            Vehicle.dealership_id == dealership_id,
        )
        .with_for_update()
    )


def list_for_vehicle(
    db: Session,
    dealership_id: int,
    vehicle_id: int,
) -> list[VehicleImage]:
    statement = (
        select(VehicleImage)
        .where(
            VehicleImage.dealership_id == dealership_id,
            VehicleImage.vehicle_id == vehicle_id,
        )
        .order_by(VehicleImage.position, VehicleImage.id)
    )
    return list(db.scalars(statement))


def create(db: Session, image: VehicleImage) -> VehicleImage:
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


def save_positions(
    db: Session,
    images: list[VehicleImage],
) -> list[VehicleImage]:
    for position, image in enumerate(images):
        image.position = position
        db.add(image)
    db.commit()
    return images


def delete(
    db: Session,
    image: VehicleImage,
    remaining_images: list[VehicleImage],
) -> None:
    db.delete(image)
    for position, remaining_image in enumerate(remaining_images):
        remaining_image.position = position
        db.add(remaining_image)
    db.commit()
