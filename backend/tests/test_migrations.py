import pytest
from alembic.script import ScriptDirectory

from app.db.base import Base
from app.db.migrations import get_alembic_config

pytestmark = pytest.mark.no_db


def test_alembic_configuration_and_head_revision() -> None:
    alembic_cfg = get_alembic_config()
    assert alembic_cfg is not None

    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    head_rev = heads[0]
    assert head_rev == "f871c43b2a19"

    head_revision_obj = script.get_revision(head_rev)
    assert head_revision_obj is not None
    assert head_revision_obj.down_revision == "d45e22bb9a73"

    audit_rev = script.get_revision("d45e22bb9a73")
    assert audit_rev is not None
    assert audit_rev.down_revision == "c34d11aa8f62"

    prev_rev = script.get_revision("c34d11aa8f62")
    assert prev_rev is not None
    assert prev_rev.down_revision == "eb80591937f2"

    base_rev = script.get_revision("eb80591937f2")
    assert base_rev is not None
    assert base_rev.down_revision is None


def test_alembic_models_metadata_coverage() -> None:
    import app.models  # noqa: F401

    table_names = set(Base.metadata.tables.keys())
    expected_tables = {
        "dealerships",
        "users",
        "refresh_tokens",
        "revoked_access_tokens",
        "user_token_versions",
        "password_reset_tokens",
        "staff_invitations",
        "brands",
        "vehicles",
        "vehicle_images",
        "test_drive_settings",
        "test_drive_slots",
        "test_drive_bookings",
        "knowledge_documents",
        "knowledge_chunks",
        "audit_logs",
    }
    assert expected_tables.issubset(table_names)
