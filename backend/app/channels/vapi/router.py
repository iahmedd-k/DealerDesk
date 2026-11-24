import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.channels.vapi.schemas import (
    VapiOutboundCallRequest,
    VapiServerMessage,
    VapiToolResponse,
    VapiToolResult,
)
from app.channels.vapi.service import get_vapi_service
from app.db.session import get_db
from app.models.workspace import Dealership

logger = logging.getLogger("dealerdesk.channels.vapi")

router = APIRouter()


def _get_active_dealership(db: Session, dealership_id: int | None = None) -> Dealership:
    try:
        query = db.query(Dealership).filter(Dealership.is_active.is_(True))
        if dealership_id:
            dealership = query.filter(Dealership.id == dealership_id).first()
        else:
            dealership = query.first()

        if dealership:
            return dealership
    except Exception as exc:
        logger.warning("Could not query active dealership: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass

    # Fallback dummy representation if running in test / without seeded DB
    return Dealership(
        id=1,
        name="DealerDesk Motors",
        address="100 Auto Mall Parkway",
        phone="+1 (555) 234-5678",
        is_active=True,
    )


@router.get(
    "/webhook",
    summary="Vapi Voice Webhook Health Check",
    description="Confirms that the Vapi voice channel adapter is online.",
)
async def vapi_webhook_health() -> dict[str, Any]:
    return {
        "status": "online",
        "channel": "voice",
        "provider": "vapi",
        "endpoint": "POST /webhook",
    }


@router.post(
    "/webhook",
    summary="Vapi Server Webhook",
    description="Handles Vapi events: assistant-request, tool-calls, and end-of-call-report.",
)
async def vapi_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_vapi_secret: str | None = Header(None, alias="x-vapi-secret"),
) -> dict[str, Any]:
    """
    Main webhook receiver for Vapi Voice Agent.
    Executes function tools (inventory search, slots, booking) and logs call reports.
    """
    service = get_vapi_service()

    # Verify secret if configured
    configured_secret = (
        service.settings.vapi_webhook_secret.get_secret_value()
        if service.settings.vapi_webhook_secret
        else None
    )
    if configured_secret and x_vapi_secret != configured_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Vapi webhook secret header",
        )

    try:
        body = await request.json()
    except Exception as exc:
        logger.warning("Could not parse Vapi JSON: %s", exc)
        return {"status": "error", "message": "Invalid JSON body"}

    message = body.get("message", {})
    msg_type = message.get("type", "")
    logger.info("Received Vapi webhook event: %s", msg_type)

    dealership = _get_active_dealership(db)

    # 1. Dynamic Assistant Configuration Request
    if msg_type == "assistant-request":
        logger.info("Returning dynamic assistant spec for dealership %s", dealership.name)
        spec = service.get_vapi_assistant_spec(dealership)
        return {"assistant": spec}

    # 2. Tool / Function Calls from Vapi Voice Agent
    elif msg_type in {"tool-calls", "function-call"}:
        tool_calls = (
            message.get("toolCalls")
            or message.get("toolCallList")
            or []
        )

        # Handle single function-call format
        if not tool_calls and "functionCall" in message:
            fc = message["functionCall"]
            tool_calls = [{"id": "fc_0", "function": fc}]

        results: list[dict[str, Any]] = []
        for tc in tool_calls:
            tc_id = tc.get("id", "call_default")
            fn = tc.get("function", {})
            fn_name = fn.get("name", "")
            fn_args = fn.get("arguments", {})

            tool_output = service.execute_tool(
                name=fn_name,
                arguments=fn_args,
                db=db,
                dealership=dealership,
            )
            results.append({
                "toolCallId": tc_id,
                "result": str(tool_output) if not isinstance(tool_output, (dict, list)) else tool_output,
            })

        return {"results": results}

    # 3. Call Finished & Transcript Report
    elif msg_type in {"end-of-call-report", "call-ended"}:
        res = service.handle_end_of_call_report(db, message, dealership)
        return {"status": "ok", "details": res}

    # 4. Status updates, speech-update, transcript events
    return {"status": "ok", "message": f"Processed {msg_type}"}


@router.get(
    "/assistant-spec",
    summary="Get Vapi Assistant Configuration",
    description="Returns full Vapi assistant JSON schema with all tool definitions to import into Vapi Console.",
)
async def get_assistant_spec(
    dealership_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = get_vapi_service()
    dealership = _get_active_dealership(db, dealership_id)
    return service.get_vapi_assistant_spec(dealership)


@router.post(
    "/call",
    summary="Trigger Outbound Vapi Call",
    description="Initiates an autonomous outbound telephone call to a customer using Vapi REST API.",
)
async def trigger_vapi_outbound_call(
    payload: VapiOutboundCallRequest,
) -> dict[str, Any]:
    service = get_vapi_service()
    try:
        call_res = await service.trigger_outbound_call(
            phone_number=payload.phone_number,
            customer_name=payload.customer_name,
            custom_first_message=payload.custom_first_message,
            assistant_id=payload.assistant_id,
        )
        return {"status": "dispatched", "call": call_res}
    except Exception as exc:
        logger.error("Outbound Vapi call initiation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
