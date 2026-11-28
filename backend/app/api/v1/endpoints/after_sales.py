from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.roles import STAFF_ROLES
from app.db.session import get_db
from app.dependencies.workspace import require_dealership_roles
from app.models.service import ServiceAppointment, ServiceWorkOrder, VehicleWarranty
from app.models.user import User
from app.schemas.after_sales import (
    ServiceAppointmentCreate,
    ServiceAppointmentResponse,
    ServiceAppointmentUpdate,
    ServiceWorkOrderCreate,
    ServiceWorkOrderResponse,
    ServiceWorkOrderUpdate,
    VehicleWarrantyCreate,
    VehicleWarrantyResponse,
    VehicleWarrantyUpdate,
)
from app.services import after_sales_service


router = APIRouter(
    prefix="/dealerships/{dealership_id}",
    tags=["After-sales Service"],
)


@router.get(
    "/service-appointments",
    response_model=list[ServiceAppointmentResponse],
)
def list_service_appointments(
    dealership_id: int,
    appointment_status: Literal[
        "scheduled", "confirmed", "completed", "cancelled", "no_show"
    ]
    | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[ServiceAppointment]:
    return after_sales_service.list_appointments(
        db,
        dealership_id,
        current_user,
        status=appointment_status,
    )


@router.post(
    "/service-appointments",
    response_model=ServiceAppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_appointment(
    dealership_id: int,
    payload: ServiceAppointmentCreate,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> ServiceAppointment:
    return after_sales_service.create_appointment(
        db,
        dealership_id,
        current_user,
        payload,
    )


@router.patch(
    "/service-appointments/{appointment_id}",
    response_model=ServiceAppointmentResponse,
)
def update_service_appointment(
    dealership_id: int,
    appointment_id: int,
    payload: ServiceAppointmentUpdate,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> ServiceAppointment:
    return after_sales_service.update_appointment(
        db,
        dealership_id,
        appointment_id,
        current_user,
        payload,
    )


@router.get(
    "/service-work-orders",
    response_model=list[ServiceWorkOrderResponse],
)
def list_service_work_orders(
    dealership_id: int,
    work_order_status: Literal["open", "in_progress", "completed", "cancelled"]
    | None = Query(default=None, alias="status"),
    follow_up_due: bool = Query(default=False),
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[ServiceWorkOrder]:
    return after_sales_service.list_work_orders(
        db,
        dealership_id,
        current_user,
        status=work_order_status,
        follow_up_due=follow_up_due,
    )


@router.post(
    "/service-work-orders",
    response_model=ServiceWorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_work_order(
    dealership_id: int,
    payload: ServiceWorkOrderCreate,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> ServiceWorkOrder:
    return after_sales_service.create_work_order(
        db,
        dealership_id,
        current_user,
        payload,
    )


@router.patch(
    "/service-work-orders/{work_order_id}",
    response_model=ServiceWorkOrderResponse,
)
def update_service_work_order(
    dealership_id: int,
    work_order_id: int,
    payload: ServiceWorkOrderUpdate,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> ServiceWorkOrder:
    return after_sales_service.update_work_order(
        db,
        dealership_id,
        work_order_id,
        current_user,
        payload,
    )


@router.get(
    "/vehicle-warranties",
    response_model=list[VehicleWarrantyResponse],
)
def list_vehicle_warranties(
    dealership_id: int,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> list[VehicleWarranty]:
    return after_sales_service.list_warranties(db, dealership_id, current_user)


@router.post(
    "/vehicle-warranties",
    response_model=VehicleWarrantyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_vehicle_warranty(
    dealership_id: int,
    payload: VehicleWarrantyCreate,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> VehicleWarranty:
    return after_sales_service.create_warranty(
        db,
        dealership_id,
        current_user,
        payload,
    )


@router.patch(
    "/vehicle-warranties/{warranty_id}",
    response_model=VehicleWarrantyResponse,
)
def update_vehicle_warranty(
    dealership_id: int,
    warranty_id: int,
    payload: VehicleWarrantyUpdate,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
) -> VehicleWarranty:
    return after_sales_service.update_warranty(
        db,
        dealership_id,
        warranty_id,
        current_user,
        payload,
    )
