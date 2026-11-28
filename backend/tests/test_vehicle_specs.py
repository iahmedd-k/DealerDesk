from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.errors import UnprocessableEntityError
from app.models.workspace import Vehicle
from app.schemas.workspace import (
    VehicleCreateRequest,
    VehicleResponse,
    VehicleStaffResponse,
)
from app.services import vehicle_service

pytestmark = pytest.mark.no_db


def test_vehicle_vin_is_normalized_and_checked() -> None:
    payload = VehicleCreateRequest(
        brand_id=1,
        model="Accord",
        model_year=2024,
        price="32000.00",
        stock_number="A-104",
        vin="1hgcm82633a004352",
    )
    assert payload.vin == "1HGCM82633A004352"

    with pytest.raises(ValueError, match="17 valid letters or digits"):
        VehicleCreateRequest(
            brand_id=1,
            model="Accord",
            model_year=2024,
            price="32000.00",
            stock_number="A-105",
            vin="1hgcm82633a00435i",
        )


def test_vin_decoder_maps_nhtsa_response(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "Results": [
                    {
                        "Make": "Honda",
                        "Model": "Accord",
                        "ModelYear": "2024",
                        "Trim": "EX",
                        "FuelTypePrimary": "Gasoline",
                        "DriveType": "FWD/Front-Wheel Drive",
                        "TransmissionStyle": "Continuously Variable Transmission",
                        "BodyClass": "Sedan",
                    }
                ]
            }

    monkeypatch.setattr(
        vehicle_service.httpx,
        "get",
        lambda *_args, **_kwargs: FakeResponse(),
    )

    decoded = vehicle_service.decode_vin("1hgcm82633a004352")

    assert decoded == {
        "vin": "1HGCM82633A004352",
        "make": "Honda",
        "model": "Accord",
        "model_year": 2024,
        "variant": "EX",
        "fuel_type": "Gasoline",
        "drivetrain": "FWD/Front-Wheel Drive",
        "transmission": "Continuously Variable Transmission",
        "body_class": "Sedan",
    }


def test_vin_decoder_rejects_malformed_vin_before_network_call(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("VIN validation should happen before the request")

    monkeypatch.setattr(vehicle_service.httpx, "get", fail_if_called)
    with pytest.raises(UnprocessableEntityError, match="17 valid letters or digits"):
        vehicle_service.decode_vin("BAD-VIN")


def test_vehicle_stock_details_are_staff_only_and_include_age() -> None:
    vehicle = Vehicle(
        id=1,
        dealership_id=1,
        brand_id=1,
        make="Honda",
        model="Accord",
        model_year=2024,
        price=Decimal("32000.00"),
        acquisition_cost=Decimal("28000.00"),
        location="Showroom A",
        reconditioning_status="complete",
        acquired_at=datetime.now(timezone.utc) - timedelta(days=40),
        stock_number="A-104",
        is_available=True,
        status="available",
        test_drive_enabled=False,
        images=[],
        status_history=[],
    )

    public_response = VehicleResponse.model_validate(vehicle).model_dump()
    staff_response = VehicleStaffResponse.model_validate(vehicle).model_dump()

    assert "acquisition_cost" not in public_response
    assert "location" not in public_response
    assert staff_response["acquisition_cost"] == Decimal("28000.00")
    assert staff_response["location"] == "Showroom A"
    assert staff_response["days_in_stock"] == 40
