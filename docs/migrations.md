# Database Migrations with Alembic

DealerDesk uses **Alembic** to manage database schema migrations, revision history, and rollbacks against PostgreSQL.
The current revision chain includes vehicle images, audit logs, and the conversion of
vehicle prices to `numeric(12,2)`.

---

## 1. Structure

```text
backend/
├── alembic.ini                   # Alembic configuration file
├── alembic/
│   ├── env.py                    # Environment runtime: loads app settings & models
│   ├── script.py.mako            # Template for new migration revisions
│   └── versions/                 # Versioned migration scripts
│       └── eb80591937f2_initial_schema.py
```

---

## 2. Configuration & Model Integration

* `alembic/env.py` dynamically resolves settings via `app.core.config.get_settings()`, reading:
  * `DATABASE_URL` (or `SUPABASE_CONNECTION_STRING`)
  * `DATABASE_SCHEMA` (sets `search_path` and `version_table_schema` when a custom schema like `dealerdesk_test` is active)
* All SQLAlchemy declarative models are imported from `app.models` so `target_metadata = Base.metadata` tracks all tables, constraints, and indexes.

---

## 3. Common Commands

All commands should be run from `backend/`:

### Check current state & history

```powershell
cd backend
alembic current
alembic heads
alembic history --verbose
```

### Apply migrations (Upgrade)

Upgrade to the latest available revision:
```powershell
cd backend
alembic upgrade head
```

Upgrade by one revision:
```powershell
alembic upgrade +1
```

### Roll back migrations (Downgrade)

Revert the most recent migration:
```powershell
cd backend
alembic downgrade -1
```

Revert all migrations back to an empty base state:
```powershell
alembic downgrade base
```

### Generate a new migration

When modifying or adding models in `app/models/`:

```powershell
cd backend
alembic revision --autogenerate -m "add_table_or_column_name"
```

Review the newly generated script in `backend/alembic/versions/` and apply with `alembic upgrade head`.

---

## 4. Programmatic Execution in Application Lifespan

The FastAPI application lifespan in `backend/app/main.py` automatically runs `run_alembic_upgrade("head")` at startup:

```python
from app.db.migrations import run_alembic_upgrade

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        run_alembic_upgrade("head")
    except Exception:
        # Fallback to metadata create_all for test environments
        ...
```

Programmatic helpers are available in `backend/app/db/migrations.py`:
* `run_alembic_upgrade(revision: str = "head")`
* `run_alembic_downgrade(revision: str = "-1")`
* `stamp_alembic_revision(revision: str = "head")`
