from fastapi import APIRouter

from app.api.v1.endpoints.assistant import router as assistant_router
from app.api.v1.endpoints.audit import router as audit_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.brands import router as brands_router
from app.api.v1.endpoints.dealerships import router as dealerships_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.knowledge import router as knowledge_router
from app.api.v1.endpoints.staff import router as staff_router
from app.api.v1.endpoints.testdrive import router as test_drive_router
from app.api.v1.endpoints.vehicles import router as vehicles_router


router = APIRouter(prefix="/api/v1")
router.include_router(assistant_router)
router.include_router(audit_router)
router.include_router(auth_router)
router.include_router(brands_router)
router.include_router(dealerships_router)
router.include_router(health_router)
router.include_router(knowledge_router)
router.include_router(staff_router)
router.include_router(test_drive_router)
router.include_router(vehicles_router)
