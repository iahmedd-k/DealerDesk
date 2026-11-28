from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text


def get_alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parents[2]
    ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return alembic_cfg


def run_alembic_upgrade(revision: str = "head") -> None:
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, revision)


def run_alembic_downgrade(revision: str = "-1") -> None:
    alembic_cfg = get_alembic_config()
    command.downgrade(alembic_cfg, revision)


def stamp_alembic_revision(revision: str = "head") -> None:
    alembic_cfg = get_alembic_config()
    command.stamp(alembic_cfg, revision)


def ensure_dealership_subscription_columns(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(32) DEFAULT 'pro'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(32) DEFAULT 'active'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS monthly_price NUMERIC(10, 2) DEFAULT 499.00"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS max_brands INTEGER DEFAULT 10"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS max_vehicles INTEGER DEFAULT 250"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
            )
        )


def ensure_security_and_idempotency_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP WITH TIME ZONE"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN DEFAULT FALSE"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS email_verification_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash VARCHAR(64) NOT NULL UNIQUE,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    used_at TIMESTAMP WITH TIME ZONE
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_email_verification_tokens_user_id ON email_verification_tokens (user_id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_email_verification_tokens_expires_at ON email_verification_tokens (expires_at)"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    id BIGSERIAL PRIMARY KEY,
                    scope_key VARCHAR(64) NOT NULL UNIQUE,
                    request_hash VARCHAR(64) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
                    status_code INTEGER,
                    headers JSONB,
                    response_body TEXT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    locked_until TIMESTAMP WITH TIME ZONE NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_idempotency_keys_expires_at ON idempotency_keys (expires_at)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_idempotency_keys_status ON idempotency_keys (status)"
            )
        )


def ensure_channel_and_hold_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE dealerships ADD COLUMN IF NOT EXISTS whatsapp_number VARCHAR(20)")
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_dealerships_whatsapp_number ON dealerships (whatsapp_number) WHERE whatsapp_number IS NOT NULL"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    dealership_id INTEGER NOT NULL REFERENCES dealerships(id) ON DELETE CASCADE,
                    channel VARCHAR(32) NOT NULL,
                    channel_user_id VARCHAR(128) NOT NULL,
                    customer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    channel_metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_dealership_channel ON conversations (dealership_id, channel)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_channel_user ON conversations (channel, channel_user_id)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE conversations ALTER COLUMN channel_user_id TYPE VARCHAR(320)"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    sender_type VARCHAR(32) NOT NULL,
                    sender_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    content TEXT NOT NULL,
                    channel_metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_conversation_messages_conv_id ON conversation_messages (conversation_id)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS external_thread_id VARCHAR(256)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_conversations_email_thread ON conversations (dealership_id, channel, external_thread_id)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS external_message_id VARCHAR(256)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_messages_external_id ON conversation_messages (conversation_id, external_message_id)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE gmail_mailbox_connections ADD COLUMN IF NOT EXISTS history_id VARCHAR(128)"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_drive_slot_holds (
                    id SERIAL PRIMARY KEY,
                    dealership_id INTEGER NOT NULL REFERENCES dealerships(id) ON DELETE CASCADE,
                    slot_id INTEGER NOT NULL REFERENCES test_drive_slots(id) ON DELETE CASCADE,
                    customer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    identifier VARCHAR(128) NOT NULL,
                    hold_token VARCHAR(64) NOT NULL UNIQUE,
                    status VARCHAR(24) NOT NULL DEFAULT 'held',
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_slot_holds_slot_active ON test_drive_slot_holds (slot_id, status)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_slot_holds_expires_at ON test_drive_slot_holds (expires_at)"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS twilio_webhook_receipts (
                    id SERIAL PRIMARY KEY,
                    message_sid VARCHAR(64) NOT NULL UNIQUE,
                    dealership_id INTEGER NOT NULL REFERENCES dealerships(id) ON DELETE CASCADE,
                    status VARCHAR(24) NOT NULL DEFAULT 'processing',
                    response_text TEXT,
                    attempts INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_twilio_webhook_receipts_dealership_id ON twilio_webhook_receipts (dealership_id)"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS twilio_delivery_statuses (
                    id SERIAL PRIMARY KEY,
                    message_sid VARCHAR(64) NOT NULL UNIQUE,
                    dealership_id INTEGER NOT NULL REFERENCES dealerships(id) ON DELETE CASCADE,
                    recipient VARCHAR(32) NOT NULL,
                    status VARCHAR(24) NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_twilio_delivery_statuses_dealership_id ON twilio_delivery_statuses (dealership_id)"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS otp_verifications (
                    id SERIAL PRIMARY KEY,
                    dealership_id INTEGER NOT NULL REFERENCES dealerships(id) ON DELETE CASCADE,
                    channel VARCHAR(32) NOT NULL,
                    identifier VARCHAR(128) NOT NULL,
                    otp_hash VARCHAR(64) NOT NULL,
                    purpose VARCHAR(32) NOT NULL DEFAULT 'test_drive_booking',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    verified_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_otp_identifier_purpose ON otp_verifications (identifier, purpose)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_otp_expires_at ON otp_verifications (expires_at)"
            )
        )


def ensure_vehicle_brand_associations(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS brand_id INTEGER")
        )
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_vehicles_brand_id
                ON vehicles (brand_id)
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_brand_dealership_name_active
                ON brands (dealership_id, lower(name))
                WHERE is_deleted = FALSE
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO brands (dealership_id, name, is_active, is_deleted)
                SELECT DISTINCT ON (dealership_id, lower(trim(make)))
                    dealership_id,
                    trim(make),
                    TRUE,
                    FALSE
                FROM vehicles
                WHERE nullif(trim(make), '') IS NOT NULL
                ORDER BY dealership_id, lower(trim(make)), id
                ON CONFLICT DO NOTHING
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE vehicles AS vehicle
                SET brand_id = brand.id
                FROM brands AS brand
                WHERE vehicle.brand_id IS NULL
                    AND brand.dealership_id = vehicle.dealership_id
                    AND lower(brand.name) = lower(trim(vehicle.make))
                    AND brand.is_deleted = FALSE
                """
            )
        )
        unassociated_count = connection.scalar(
            text("SELECT count(*) FROM vehicles WHERE brand_id IS NULL")
        )
        if unassociated_count:
            raise RuntimeError(
                "Could not associate "
                f"{unassociated_count} existing vehicle(s) with a brand; "
                "check for blank vehicle makes."
            )
        connection.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conrelid = 'vehicles'::regclass
                          AND conname = 'fk_vehicles_brand_id_brands'
                    ) THEN
                        ALTER TABLE vehicles
                        ADD CONSTRAINT fk_vehicles_brand_id_brands
                        FOREIGN KEY (brand_id) REFERENCES brands(id)
                        ON DELETE RESTRICT;
                    END IF;
                END
                $$
                """
            )
        )
        connection.execute(
            text("ALTER TABLE vehicles ALTER COLUMN brand_id SET NOT NULL")
        )


def ensure_vehicle_lifecycle_and_audit_columns(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'available'"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_vehicles_status ON vehicles (status)"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS vehicle_status_history (
                    id SERIAL PRIMARY KEY,
                    dealership_id INTEGER NOT NULL REFERENCES dealerships(id) ON DELETE CASCADE,
                    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
                    changed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    previous_status VARCHAR(32) NOT NULL,
                    new_status VARCHAR(32) NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_vehicle_status_history_vehicle_id ON vehicle_status_history (vehicle_id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_vehicle_status_history_dealership_id ON vehicle_status_history (dealership_id)"
            )
        )


def ensure_vehicle_spec_columns(engine: Engine) -> None:
    with engine.begin() as connection:
        for column_name, column_type in (
            ("vin", "VARCHAR(17)"),
            ("mileage", "INTEGER"),
            ("transmission", "VARCHAR(32)"),
            ("fuel_type", "VARCHAR(32)"),
            ("drivetrain", "VARCHAR(32)"),
            ("exterior_color", "VARCHAR(64)"),
            ("interior_color", "VARCHAR(64)"),
            ("acquisition_cost", "NUMERIC(12, 2)"),
            ("location", "VARCHAR(100)"),
            ("reconditioning_status", "VARCHAR(24) NOT NULL DEFAULT 'not_required'"),
            ("acquired_at", "TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()"),
        ):
            connection.execute(
                text(
                    f"ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
                )
            )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_vehicle_dealership_vin ON vehicles (dealership_id, vin)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_vehicles_acquired_at ON vehicles (acquired_at)"
            )
        )


def ensure_crm_lead_enhancements(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS lost_reason VARCHAR(32)")
        )
        for column in (
            "email_consent",
            "sms_consent",
            "whatsapp_consent",
        ):
            connection.execute(
                text(
                    f"ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS {column} BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
        for column in (
            "email_consented_at",
            "email_opted_out_at",
            "sms_consented_at",
            "sms_opted_out_at",
            "whatsapp_consented_at",
            "whatsapp_opted_out_at",
        ):
            connection.execute(
                text(
                    f"ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS {column} TIMESTAMP WITH TIME ZONE"
                )
            )
        connection.execute(
            text("ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS budget NUMERIC(12, 2)")
        )
        connection.execute(
            text("ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS purchase_timeline VARCHAR(64)")
        )
        connection.execute(
            text(
                "ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS conversation_id INTEGER REFERENCES conversations(id) ON DELETE SET NULL"
            )
        )
        connection.execute(
            text("ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS preferences JSONB")
        )
        connection.execute(
            text("ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS deal_value NUMERIC(12, 2)")
        )
        connection.execute(
            text("ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS deal_notes TEXT")
        )
        connection.execute(
            text(
                "ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS trade_in_vehicle VARCHAR(200)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS trade_in_value NUMERIC(12, 2)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS down_payment NUMERIC(12, 2)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS apr_percent NUMERIC(5, 2)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE customer_leads ADD COLUMN IF NOT EXISTS loan_term_months INTEGER"
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS lead_activities (
                    id SERIAL PRIMARY KEY,
                    dealership_id INTEGER NOT NULL REFERENCES dealerships(id) ON DELETE CASCADE,
                    lead_id INTEGER NOT NULL REFERENCES customer_leads(id) ON DELETE CASCADE,
                    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    activity_type VARCHAR(32) NOT NULL,
                    summary TEXT NOT NULL,
                    details JSONB,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_lead_activities_lead_created ON lead_activities (lead_id, created_at)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_lead_activities_dealership_id ON lead_activities (dealership_id)"
            )
        )


def ensure_notification_ledger_table(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    id SERIAL PRIMARY KEY,
                    dealership_id INTEGER NOT NULL REFERENCES dealerships(id) ON DELETE CASCADE,
                    booking_id INTEGER REFERENCES test_drive_bookings(id) ON DELETE CASCADE,
                    notification_type VARCHAR(48) NOT NULL,
                    channel VARCHAR(24) NOT NULL DEFAULT 'email',
                    recipient VARCHAR(320) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    error_message TEXT,
                    sent_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_notification_booking_type UNIQUE (booking_id, notification_type)
                )
                """
            )
        )
        connection.execute(
            text(
                "ALTER TABLE notification_deliveries ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE notification_deliveries ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP WITH TIME ZONE"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE notification_deliveries ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMP WITH TIME ZONE"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_notification_deliveries_dealership ON notification_deliveries (dealership_id, created_at)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_notification_deliveries_next_retry_at ON notification_deliveries (next_retry_at)"
            )
        )


def ensure_test_drive_booking_outcomes(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE test_drive_bookings ADD COLUMN IF NOT EXISTS assigned_to_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE test_drive_bookings ADD COLUMN IF NOT EXISTS outcome_at TIMESTAMP WITH TIME ZONE"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE test_drive_bookings ADD COLUMN IF NOT EXISTS outcome_notes TEXT"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_test_drive_bookings_assigned_to_user_id ON test_drive_bookings (assigned_to_user_id)"
            )
        )


def ensure_governance_and_outbox_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_available BOOLEAN NOT NULL DEFAULT TRUE")
        )
        connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS availability_note VARCHAR(255)")
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS outbox_events (
                    id SERIAL PRIMARY KEY,
                    dealership_id INTEGER NOT NULL REFERENCES dealerships(id) ON DELETE CASCADE,
                    event_type VARCHAR(64) NOT NULL,
                    aggregate_type VARCHAR(48) NOT NULL,
                    aggregate_id VARCHAR(64) NOT NULL,
                    payload JSONB NOT NULL,
                    target_webhook_url VARCHAR(500),
                    status VARCHAR(24) NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    next_retry_at TIMESTAMP WITH TIME ZONE,
                    delivered_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_outbox_events_dealership_status ON outbox_events (dealership_id, status)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_outbox_events_status_retry ON outbox_events (status, next_retry_at)"
            )
        )


def ensure_gmail_sync_columns(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE gmail_mailbox_connections ADD COLUMN IF NOT EXISTS next_sync_at TIMESTAMP WITH TIME ZONE"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE gmail_mailbox_connections ADD COLUMN IF NOT EXISTS sync_attempts INTEGER NOT NULL DEFAULT 0"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE gmail_mailbox_connections ADD COLUMN IF NOT EXISTS last_sync_error VARCHAR(128)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_gmail_mailbox_connections_next_sync_at ON gmail_mailbox_connections (next_sync_at)"
            )
        )
