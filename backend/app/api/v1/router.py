from fastapi import APIRouter

from app.api.v1.endpoints.assistant import router as assistant_router
from app.api.v1.endpoints.audit import router as audit_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.brands import router as brands_router
from app.api.v1.endpoints.channels import router as channels_router
from app.api.v1.endpoints.conversations import router as conversations_router
from app.api.v1.endpoints.dealerships import router as dealerships_router
from app.api.v1.endpoints.governance import router as governance_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.leads import router as leads_router
from app.api.v1.endpoints.knowledge import router as knowledge_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.orchestration import router as orchestration_router
from app.api.v1.endpoints.sales_agent import router as sales_agent_router
from app.api.v1.endpoints.staff import router as staff_router
from app.api.v1.endpoints.testdrive import router as test_drive_router
from app.api.v1.endpoints.vehicles import router as vehicles_router
from app.channels.vapi.router import router as vapi_channel_router
from app.channels.whatsapp.router import router as whatsapp_channel_router


router = APIRouter(prefix="/api/v1")
router.include_router(assistant_router)
router.include_router(audit_router)
router.include_router(auth_router)
router.include_router(brands_router)
router.include_router(channels_router)
router.include_router(conversations_router)
router.include_router(dealerships_router)
router.include_router(governance_router)
router.include_router(health_router)
router.include_router(leads_router)
router.include_router(knowledge_router)
router.include_router(notifications_router)
router.include_router(orchestration_router)
router.include_router(sales_agent_router)
router.include_router(staff_router)
router.include_router(test_drive_router)
router.include_router(vehicles_router)
router.include_router(
    whatsapp_channel_router,
    prefix="/channels/whatsapp",
    tags=["WhatsApp Channel"],
)
router.include_router(
    vapi_channel_router,
    prefix="/channels/vapi",
    tags=["Vapi Voice Channel"],
)
