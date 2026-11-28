from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.v1.endpoints import vehicles as vehicles_endpoint
from app.core.errors import BadRequestError
from app.schemas.workspace import CSVVehicleImportRequest

pytestmark = pytest.mark.no_db


def test_vehicle_csv_preview_identifies_upserts_without_overwriting_omitted_fields() -> None:
    existing = SimpleNamespace(id=21, stock_number="STK-21", vin=None)
    db = MagicMock()
    db.scalars.side_effect = [
        [SimpleNamespace(id=1)],
        [existing],
    ]
    payload = CSVVehicleImportRequest(
        mode="upsert",
        csv_content=(
            "brand_id,model,model_year,price,stock_number,location\n"
            "1,Camry,2025,32000,STK-21,Showroom A\n"
        ),
    )

    prepared, errors = vehicles_endpoint._prepare_vehicle_import(db, 1, payload)

    assert errors == []
    assert len(prepared) == 1
    row_number, vehicle_payload, matched_vehicle = prepared[0]
    assert row_number == 2
    assert matched_vehicle is existing
    assert vehicle_payload.location == "Showroom A"
    assert "status" not in vehicle_payload.model_fields_set
    assert "test_drive_enabled" not in vehicle_payload.model_fields_set
    assert "reconditioning_status" not in vehicle_payload.model_fields_set


def test_vehicle_csv_preview_rejects_duplicate_stock_numbers_in_file() -> None:
    db = MagicMock()
    db.scalars.side_effect = [
        [SimpleNamespace(id=1)],
        [],
    ]
    payload = CSVVehicleImportRequest(
        csv_content=(
            "brand_id,model,model_year,price,stock_number\n"
            "1,Camry,2025,32000,STK-21\n"
            "1,Corolla,2025,28000,STK-21\n"
        ),
    )

    prepared, errors = vehicles_endpoint._prepare_vehicle_import(db, 1, payload)

    assert len(prepared) == 1
    assert errors == [
        {"row": 3, "error": "Duplicate stock_number in this CSV file"}
    ]


def test_vehicle_csv_import_rejects_duplicate_headers() -> None:
    payload = CSVVehicleImportRequest(
        csv_content=(
            "brand_id,model,model_year,price,stock_number,STOCK_NUMBER\n"
            "1,Camry,2025,32000,STK-21,STK-22\n"
        ),
    )

    with pytest.raises(BadRequestError, match="CSV column names must be unique"):
        vehicles_endpoint._prepare_vehicle_import(MagicMock(), 1, payload)
