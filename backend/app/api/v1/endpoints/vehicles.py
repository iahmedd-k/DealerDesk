import csv
from io import StringIO
import math
from decimal import Decimal
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.redis import redis_client
from app.core.errors import ApplicationError, BadRequestError, PayloadTooLargeError
from app.core.roles import DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE, SALES_REP_ROLE, STAFF_ROLES
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.workspace import require_dealership_roles
from app.models.user import User
from app.models.workspace import Brand, Vehicle, VehicleImage
from app.schemas.workspace import (
    CSVVehicleImportRequest,
    VehicleCreateRequest,
    VehicleImageResponse,
    VehicleImageUpdateRequest,
    VehicleResponse,
    VehicleStatusHistoryResponse,
    VehicleStatusTransitionRequest,
    VehicleStaffResponse,
    VehicleUpdateRequest,
)
from app.services import vehicle_service
from app.services import vehicle_image_service


router = APIRouter(prefix="/dealerships/{dealership_id}/vehicles", tags=["Vehicles"])


@router.get("/vin/{vin}/decode")
def decode_vehicle_vin(
    dealership_id: int,
    vin: str,
    current_user: User = Depends(require_dealership_roles(*STAFF_ROLES)),
) -> dict[str, str | int | None]:
    return vehicle_service.decode_vin(vin)


@router.post("/import")
def import_vehicles_from_csv(
    dealership_id: int,
    payload: CSVVehicleImportRequest,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    prepared, errors = _prepare_vehicle_import(db, dealership_id, payload)
    created = 0
    updated = 0
    for row_number, vehicle_payload, existing in prepared:
        try:
            if existing is None:
                vehicle_service.create_vehicle(
                    db, dealership_id, current_user, vehicle_payload
                )
                created += 1
            else:
                update_payload = VehicleUpdateRequest.model_validate(
                    vehicle_payload.model_dump(
                        exclude_none=True,
                        include=vehicle_payload.model_fields_set,
                    )
                )
                vehicle_service.update_vehicle(
                    db,
                    dealership_id,
                    existing.id,
                    current_user,
                    update_payload,
                )
                updated += 1
        except ApplicationError as exc:
            errors.append({"row": row_number, "error": exc.detail})

    if created or updated:
        redis_client.delete(
            f"dealerdesk:public:vehicles:{dealership_id}",
            f"dealerdesk:staff:vehicles:{dealership_id}",
            f"dealerdesk:reports:summary:{dealership_id}",
        )
    return {
        "created": created,
        "updated": updated,
        "failed": len(errors),
        "errors": errors,
    }


@router.post("/import/preview")
def preview_vehicle_csv_import(
    dealership_id: int,
    payload: CSVVehicleImportRequest,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    prepared, errors = _prepare_vehicle_import(db, dealership_id, payload)
    rows = [
        {
            "row": row_number,
            "action": "update" if existing is not None else "create",
            "stock_number": vehicle_payload.stock_number,
            "vin": vehicle_payload.vin,
        }
        for row_number, vehicle_payload, existing in prepared
    ]
    return {
        "mode": payload.mode,
        "creates": sum(row["action"] == "create" for row in rows),
        "updates": sum(row["action"] == "update" for row in rows),
        "failed": len(errors),
        "rows": rows,
        "errors": errors,
    }


def _prepare_vehicle_import(
    db: Session,
    dealership_id: int,
    payload: CSVVehicleImportRequest,
) -> tuple[list[tuple[int, VehicleCreateRequest, Vehicle | None]], list[dict[str, object]]]:
    try:
        reader = csv.DictReader(StringIO(payload.csv_content))
        normalized_headers = [
            str(header).lstrip("\ufeff").strip().lower()
            for header in (reader.fieldnames or [])
        ]
        if not normalized_headers or any(not header for header in normalized_headers):
            raise BadRequestError("CSV column names cannot be empty")
        if len(normalized_headers) != len(set(normalized_headers)):
            raise BadRequestError("CSV column names must be unique")
        headers = set(normalized_headers)
        required_headers = {"brand_id", "model", "model_year", "price", "stock_number"}
        if not required_headers.issubset(headers):
            raise BadRequestError(
                "CSV headers must include brand_id, model, model_year, price, and stock_number"
            )
        rows = list(reader)
    except csv.Error as exc:
        raise BadRequestError("CSV content could not be parsed") from exc
    if not rows:
        raise BadRequestError("CSV must contain at least one vehicle row")
    if len(rows) > 500:
        raise PayloadTooLargeError("CSV imports are limited to 500 vehicles per request")
    parsed_rows: list[tuple[int, VehicleCreateRequest]] = []
    errors: list[dict[str, object]] = []
    seen_stock_numbers: set[str] = set()
    seen_vins: set[str] = set()
    for row_number, raw_row in enumerate(rows, start=2):
        row = {
            str(key).lstrip("\ufeff").strip().lower(): (value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        vehicle_data: dict[str, object] = {
            "brand_id": row.get("brand_id", ""),
            "model": row.get("model", ""),
            "model_year": row.get("model_year", ""),
            "price": row.get("price", ""),
            "acquisition_cost": row.get("acquisition_cost") or None,
            "location": row.get("location") or None,
            "acquired_at": row.get("acquired_at") or None,
            "stock_number": row.get("stock_number", ""),
            "vin": row.get("vin") or None,
            "mileage": row.get("mileage") or None,
            "transmission": row.get("transmission") or None,
            "fuel_type": row.get("fuel_type") or None,
            "drivetrain": row.get("drivetrain") or None,
            "exterior_color": row.get("exterior_color") or None,
            "interior_color": row.get("interior_color") or None,
            "variant": row.get("variant") or None,
            "description": row.get("description") or None,
        }
        if row.get("status"):
            vehicle_data["status"] = row["status"]
        if row.get("reconditioning_status"):
            vehicle_data["reconditioning_status"] = row["reconditioning_status"]
        if row.get("test_drive_enabled"):
            vehicle_data["test_drive_enabled"] = row["test_drive_enabled"].lower() in {
                "true",
                "yes",
                "1",
            }
        try:
            vehicle_payload = VehicleCreateRequest.model_validate(vehicle_data)
        except ValidationError as exc:
            errors.append({"row": row_number, "error": exc.errors()[0]["msg"]})
            continue
        if vehicle_payload.stock_number in seen_stock_numbers:
            errors.append(
                {"row": row_number, "error": "Duplicate stock_number in this CSV file"}
            )
            continue
        if vehicle_payload.vin and vehicle_payload.vin in seen_vins:
            errors.append({"row": row_number, "error": "Duplicate VIN in this CSV file"})
            continue
        seen_stock_numbers.add(vehicle_payload.stock_number)
        if vehicle_payload.vin:
            seen_vins.add(vehicle_payload.vin)
        parsed_rows.append((row_number, vehicle_payload))

    brand_ids = {item.brand_id for _, item in parsed_rows}
    valid_brand_ids: set[int] = set()
    if parsed_rows:
        valid_brand_ids = {
            brand.id
            for brand in db.scalars(
                select(Brand).where(
                    Brand.dealership_id == dealership_id,
                    Brand.id.in_(brand_ids),
                    Brand.is_active.is_(True),
                    Brand.is_deleted.is_(False),
                )
            )
        }
    valid_rows: list[tuple[int, VehicleCreateRequest]] = []
    for row_number, vehicle_payload in parsed_rows:
        if vehicle_payload.brand_id not in valid_brand_ids:
            errors.append(
                {
                    "row": row_number,
                    "error": "brand_id must reference an active brand in this dealership",
                }
            )
        else:
            valid_rows.append((row_number, vehicle_payload))
    parsed_rows = valid_rows
    stock_numbers = [item.stock_number for _, item in parsed_rows]
    vins = [item.vin for _, item in parsed_rows if item.vin]
    match_conditions = [Vehicle.stock_number.in_(stock_numbers)]
    if vins:
        match_conditions.append(Vehicle.vin.in_(vins))
    existing_vehicles = list(
        db.scalars(
            select(Vehicle).where(
                Vehicle.dealership_id == dealership_id,
                or_(*match_conditions),
            )
        )
    ) if parsed_rows else []
    by_stock = {vehicle.stock_number: vehicle for vehicle in existing_vehicles}
    by_vin = {vehicle.vin: vehicle for vehicle in existing_vehicles if vehicle.vin}

    prepared: list[tuple[int, VehicleCreateRequest, Vehicle | None]] = []
    for row_number, vehicle_payload in parsed_rows:
        stock_match = by_stock.get(vehicle_payload.stock_number)
        vin_match = by_vin.get(vehicle_payload.vin) if vehicle_payload.vin else None
        if stock_match is not None and vin_match is not None and stock_match.id != vin_match.id:
            errors.append(
                {"row": row_number, "error": "VIN and stock_number match different vehicles"}
            )
            continue
        existing = stock_match or vin_match
        if existing is not None and payload.mode == "create":
            errors.append(
                {"row": row_number, "error": "Vehicle already exists; use upsert mode to update it"}
            )
            continue
        prepared.append((row_number, vehicle_payload, existing))
    return prepared, errors


@router.get("/public", response_model=list[VehicleResponse])
def list_public_vehicles(
    dealership_id: int,
    response: Response,
    brand_id: int | None = Query(default=None, description="Filter by brand ID"),
    min_price: Decimal | None = Query(default=None, ge=0, description="Minimum price filter"),
    max_price: Decimal | None = Query(default=None, ge=0, description="Maximum price filter"),
    search: str | None = Query(default=None, description="Search keyword in model, make, variant, or stock number"),
    sort_by: str | None = Query(default=None, description="Field to sort by (price, year, model)"),
    order: str = Query(default="asc", pattern=r"^(asc|desc)$", description="Sort order ('asc' or 'desc')"),
    page: int | None = Query(default=None, ge=1, description="Page number starting at 1"),
    page_size: int | None = Query(default=None, ge=1, le=100, description="Items per page"),
    limit: int | None = Query(default=None, ge=1, le=100),
    include_images: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[Vehicle]:
    if limit is not None and (page is not None or page_size is not None):
        raise HTTPException(
            status_code=422,
            detail="Use either limit or page/page_size, not both.",
        )

    is_unfiltered = (
        brand_id is None
        and min_price is None
        and max_price is None
        and search is None
        and sort_by is None
        and page is None
        and page_size is None
        and limit is None
        and include_images
    )
    cache_key = f"dealerdesk:public:vehicles:{dealership_id}"
    if is_unfiltered:
        cached = redis_client.get_json(cache_key)
        if isinstance(cached, list):
            return cached

    vehicles = vehicle_service.list_public_vehicles(
        db,
        dealership_id,
        brand_id=brand_id,
        min_price=min_price,
        max_price=max_price,
        search=search,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
        limit=limit,
        include_images=include_images,
    )
    if page is not None and page_size is not None:
        total = vehicle_service.count_vehicles(
            db,
            dealership_id,
            brand_id=brand_id,
            min_price=min_price,
            max_price=max_price,
            is_available=True,
            search=search,
        )
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Page"] = str(page)
        response.headers["X-Page-Size"] = str(page_size)
        response.headers["X-Total-Pages"] = str(math.ceil(total / page_size) if page_size > 0 else 1)
    if is_unfiltered:
        serialized = [VehicleResponse.model_validate(v).model_dump(mode="json") for v in vehicles]
        redis_client.set_json(cache_key, serialized, ttl_seconds=30)
        return serialized
    return vehicles


@router.post("", response_model=VehicleStaffResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    dealership_id: int,
    payload: VehicleCreateRequest,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> Vehicle:
    created = vehicle_service.create_vehicle(db, dealership_id, current_user, payload)
    redis_client.delete(
        f"dealerdesk:public:vehicles:{dealership_id}",
        f"dealerdesk:staff:vehicles:{dealership_id}",
        f"dealerdesk:reports:summary:{dealership_id}",
    )
    return created


@router.get("", response_model=list[VehicleStaffResponse])
def list_vehicles(
    dealership_id: int,
    response: Response,
    include_archived_brands: bool = False,
    brand_id: int | None = Query(default=None, description="Filter by brand ID"),
    min_price: Decimal | None = Query(default=None, ge=0, description="Minimum price filter"),
    max_price: Decimal | None = Query(default=None, ge=0, description="Maximum price filter"),
    status: str | None = Query(default=None, description="Filter by lifecycle status (available, reserved, sold, in_transit, unavailable)"),
    is_available: bool | None = Query(default=None, description="Filter by availability status"),
    test_drive_enabled: bool | None = Query(default=None, description="Filter by test drive availability"),
    fuel_type: str | None = Query(default=None, max_length=32),
    transmission: str | None = Query(default=None, max_length=32),
    drivetrain: str | None = Query(default=None, max_length=32),
    search: str | None = Query(default=None, description="Search keyword in model, make, variant, or stock number"),
    sort_by: str | None = Query(default=None, description="Field to sort by (price, year, model)"),
    order: str = Query(default="asc", pattern=r"^(asc|desc)$", description="Sort order ('asc' or 'desc')"),
    page: int | None = Query(default=None, ge=1, description="Page number starting at 1"),
    page_size: int | None = Query(default=None, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Vehicle] | list[dict]:
    is_unfiltered = (
        not include_archived_brands
        and brand_id is None
        and min_price is None
        and max_price is None
        and status is None
        and is_available is None
        and test_drive_enabled is None
        and fuel_type is None
        and transmission is None
        and drivetrain is None
        and search is None
        and sort_by is None
        and page is None
        and page_size is None
    )
    cache_key = f"dealerdesk:staff:vehicles:{dealership_id}"
    if is_unfiltered:
        cached = redis_client.get_json(cache_key)
        if isinstance(cached, list):
            return cached

    vehicles = vehicle_service.list_vehicles(
        db,
        dealership_id,
        current_user,
        include_archived_brands=include_archived_brands,
        brand_id=brand_id,
        min_price=min_price,
        max_price=max_price,
        status=status,
        is_available=is_available,
        test_drive_enabled=test_drive_enabled,
        fuel_type=fuel_type,
        transmission=transmission,
        drivetrain=drivetrain,
        search=search,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )
    if page is not None and page_size is not None:
        total = vehicle_service.count_vehicles(
            db,
            dealership_id,
            include_archived_brands=include_archived_brands,
            brand_id=brand_id,
            min_price=min_price,
            max_price=max_price,
            status=status,
            is_available=is_available,
            test_drive_enabled=test_drive_enabled,
            fuel_type=fuel_type,
            transmission=transmission,
            drivetrain=drivetrain,
            search=search,
        )
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Page"] = str(page)
        response.headers["X-Page-Size"] = str(page_size)
        response.headers["X-Total-Pages"] = str(math.ceil(total / page_size) if page_size > 0 else 1)
    if is_unfiltered:
        serialized = [VehicleResponse.model_validate(v).model_dump(mode="json") for v in vehicles]
        redis_client.set_json(cache_key, serialized, ttl_seconds=20)
        return serialized
    return vehicles


@router.get("/{vehicle_id}", response_model=VehicleStaffResponse)
def get_vehicle(
    dealership_id: int,
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Vehicle:
    return vehicle_service.get_vehicle(db, dealership_id, vehicle_id, current_user)


@router.get(
    "/{vehicle_id}/images",
    response_model=list[VehicleImageResponse],
)
def list_vehicle_images(
    dealership_id: int,
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VehicleImage]:
    return vehicle_image_service.list_images(
        db,
        dealership_id,
        vehicle_id,
        current_user,
    )


@router.post(
    "/{vehicle_id}/images",
    response_model=VehicleImageResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_vehicle_image(
    dealership_id: int,
    vehicle_id: int,
    file: UploadFile = File(...),
    alt_text: str | None = Form(default=None, max_length=255),
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> VehicleImage:
    content = file.file.read(vehicle_image_service.MAX_VEHICLE_IMAGE_SIZE + 1)
    return vehicle_image_service.upload_image(
        db,
        dealership_id,
        vehicle_id,
        current_user,
        file.content_type,
        content,
        alt_text,
    )


@router.patch(
    "/{vehicle_id}/images/{image_id}",
    response_model=VehicleImageResponse,
)
def update_vehicle_image(
    dealership_id: int,
    vehicle_id: int,
    image_id: int,
    payload: VehicleImageUpdateRequest,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> VehicleImage:
    return vehicle_image_service.update_image(
        db,
        dealership_id,
        vehicle_id,
        image_id,
        current_user,
        payload,
    )


@router.delete(
    "/{vehicle_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_vehicle_image(
    dealership_id: int,
    vehicle_id: int,
    image_id: int,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> None:
    vehicle_image_service.delete_image(
        db,
        dealership_id,
        vehicle_id,
        image_id,
        current_user,
    )


@router.patch("/{vehicle_id}", response_model=VehicleStaffResponse)
def update_vehicle(
    dealership_id: int,
    vehicle_id: int,
    payload: VehicleUpdateRequest,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> Vehicle:
    return vehicle_service.update_vehicle(
        db,
        dealership_id,
        vehicle_id,
        current_user,
        payload,
    )


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(
    dealership_id: int,
    vehicle_id: int,
    current_user: User = Depends(
        require_dealership_roles(DEALERSHIP_ADMIN_ROLE, MANAGER_ROLE)
    ),
    db: Session = Depends(get_db),
) -> None:
    vehicle_service.delete_vehicle(db, dealership_id, vehicle_id, current_user)


@router.patch("/{vehicle_id}/availability", response_model=VehicleStaffResponse)
def update_vehicle_availability(
    dealership_id: int,
    vehicle_id: int,
    available: bool,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> Vehicle:
    return vehicle_service.update_vehicle_availability(
        db,
        dealership_id,
        vehicle_id,
        current_user,
        available,
    )


@router.patch("/{vehicle_id}/status", response_model=VehicleStaffResponse)
def transition_vehicle_status(
    dealership_id: int,
    vehicle_id: int,
    payload: VehicleStatusTransitionRequest,
    current_user: User = Depends(
        require_dealership_roles(
            DEALERSHIP_ADMIN_ROLE,
            MANAGER_ROLE,
            SALES_REP_ROLE,
        )
    ),
    db: Session = Depends(get_db),
) -> Vehicle:
    return vehicle_service.transition_vehicle_status(
        db,
        dealership_id,
        vehicle_id,
        current_user,
        payload,
    )


@router.get("/{vehicle_id}/history", response_model=list[VehicleStatusHistoryResponse])
def get_vehicle_status_history(
    dealership_id: int,
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VehicleStatusHistoryResponse]:
    history_records = vehicle_service.get_vehicle_status_history(
        db,
        dealership_id,
        vehicle_id,
        current_user,
    )
    return [
        VehicleStatusHistoryResponse(
            id=item.id,
            dealership_id=item.dealership_id,
            vehicle_id=item.vehicle_id,
            changed_by_user_id=item.changed_by_user_id,
            changed_by_user_email=item.changed_by_user.email if item.changed_by_user else None,
            previous_status=item.previous_status,
            new_status=item.new_status,
            notes=item.notes,
            created_at=item.created_at,
        )
        for item in history_records
    ]
