from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.db.session import get_db
from app.dependencies.auth import get_optional_current_user
from app.models.user import User
from app.schemas.channel import (
    BookingVerificationConfirmRequest,
    BookingVerificationConfirmResponse,
    BookingVerificationInitiateRequest,
    BookingVerificationInitiateResponse,
    ConversationMessageResponse,
    ConversationResponse,
    SlotHoldCreate,
    SlotHoldResponse,
)
from app.schemas.sales_agent import SalesAgentChatRequest, SalesAgentChatResponse
from app.schemas.workspace import CustomerLeadCreateRequest, CustomerLeadResponse
from app.services import (
    conversation_service,
    customer_verification_service,
    lead_service,
    sales_agent_service,
    slot_hold_service,
)

router = APIRouter(prefix="/dealerships/{dealership_id}/sales-agent", tags=["Customer Sales Agent"])


@router.post(
    "/chat",
    response_model=SalesAgentChatResponse,
    summary="Chat with Customer Sales Agent",
    description="Conversational sales agent assisting public customers with inventory, comparisons, and test drives.",
)
@limiter.limit("30/minute")
def chat_sales_agent(
    request: Request,
    dealership_id: int,
    payload: SalesAgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> SalesAgentChatResponse:
    return sales_agent_service.chat_with_sales_agent(
        db,
        dealership_id=dealership_id,
        payload=payload,
        current_user=current_user,
    )


@router.post(
    "/chat/stream",
    summary="Stream Sales Agent responses (SSE)",
    description="Server-Sent Events streaming endpoint for the Customer Sales Agent.",
)
@limiter.limit("30/minute")
async def stream_sales_agent(
    request: Request,
    dealership_id: int,
    payload: SalesAgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> StreamingResponse:
    return StreamingResponse(
        sales_agent_service.stream_sales_agent_chat(
            db,
            dealership_id=dealership_id,
            payload=payload,
            current_user=current_user,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/slot-holds",
    response_model=SlotHoldResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Acquire a temporary test-drive slot hold",
    description="Holds a test-drive slot for 10 minutes while customer completes identity verification.",
)
def create_slot_hold(
    dealership_id: int,
    payload: SlotHoldCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> SlotHoldResponse:
    hold = slot_hold_service.acquire_slot_hold(
        db,
        dealership_id=dealership_id,
        slot_id=payload.slot_id,
        identifier=payload.identifier,
        customer_id=current_user.id if current_user else None,
        duration_minutes=payload.duration_minutes,
    )
    return SlotHoldResponse.model_validate(hold)


@router.post(
    "/leads",
    response_model=CustomerLeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Capture customer sales lead",
    description="Captures purchase intent and contact details from the customer sales journey.",
)
def create_sales_lead(
    dealership_id: int,
    payload: CustomerLeadCreateRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> CustomerLeadResponse:
    lead = lead_service.create_lead(
        db,
        dealership_id=dealership_id,
        payload=payload,
        current_user=current_user,
    )
    return CustomerLeadResponse.model_validate(lead)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ConversationMessageResponse],
    summary="Get conversation message history",
    description="Returns the message history for a persistent customer sales conversation.",
)
def get_conversation_history(
    dealership_id: int,
    conversation_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[ConversationMessageResponse]:
    messages = conversation_service.get_conversation_history(
        db,
        conversation_id=conversation_id,
        limit=limit,
    )
    return [ConversationMessageResponse.model_validate(m) for m in messages]


@router.post(
    "/verification/initiate",
    response_model=BookingVerificationInitiateResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate customer test-drive booking verification",
    description="Holds slot and dispatches single-use OTP without disclosing account existence.",
)
@limiter.limit("10/minute")
def initiate_verification(
    request: Request,
    dealership_id: int,
    payload: BookingVerificationInitiateRequest,
    db: Session = Depends(get_db),
) -> BookingVerificationInitiateResponse:
    return customer_verification_service.initiate_booking_verification(
        db,
        dealership_id=dealership_id,
        payload=payload,
    )


@router.post(
    "/verification/confirm",
    response_model=BookingVerificationConfirmResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm customer OTP and book test-drive",
    description="Verifies single-use OTP, provisions/resolves customer, and creates confirmed booking.",
)
@limiter.limit("10/minute")
def confirm_verification(
    request: Request,
    dealership_id: int,
    payload: BookingVerificationConfirmRequest,
    db: Session = Depends(get_db),
) -> BookingVerificationConfirmResponse:
    return customer_verification_service.verify_customer_and_confirm_booking(
        db,
        dealership_id=dealership_id,
        payload=payload,
    )

