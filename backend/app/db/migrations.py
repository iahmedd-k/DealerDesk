from sqlalchemy import Engine, text


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
