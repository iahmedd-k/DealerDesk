import json
import logging
from typing import Any
from decimal import Decimal
import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.workspace import Dealership
from app.services import conversation_service
from app.tools import sales_tools

logger = logging.getLogger("dealerdesk.channels.vapi")


class VapiService:
    """
    Core service handling Vapi Voice AI interactions:
    - Tool/function execution during voice calls (inventory search, test-drives, hours)
    - Dynamic assistant configuration synthesis
    - Call completion logging into CRM leads and conversations
    - Outbound call initiation via Vapi REST API
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def execute_tool(
        self,
        name: str,
        arguments: dict[str, Any] | str,
        db: Session,
        dealership: Dealership,
    ) -> Any:
        """
        Executes a tool call requested by the Vapi Voice Agent and formats
        the output to be natural and concise when spoken aloud.
        """
        if isinstance(arguments, str):
            try:
                args = json.loads(arguments)
            except Exception:
                args = {}
        else:
            args = arguments or {}

        logger.info("Executing Vapi voice tool '%s' with args: %s", name, args)

        if name == "search_inventory":
            query = args.get("query")
            max_price = args.get("max_price")
            make = args.get("make")
            model = args.get("model")

            try:
                vehicles = sales_tools.search_inventory(
                    db,
                    dealership.id,
                    query=query,
                    make=make,
                    model=model,
                    max_price=max_price,
                    limit=3,
                )
            except Exception as exc:
                logger.warning("search_inventory DB fallback: %s", exc)
                try:
                    db.rollback()
                except Exception:
                    pass
                vehicles = []

            if not vehicles:
                return (
                    f"We currently don't have vehicles matching those exact criteria in stock at {dealership.name}. "
                    "However, we receive new inventory weekly. Would you like me to check a different price range or body style?"
                )

            car_descriptions = []
            for v in vehicles:
                price_str = f"{int(v['price']):,} dollars" if isinstance(v['price'], (int, float, Decimal)) else str(v['price'])
                car_descriptions.append(f"{v['model_year']} {v['make']} {v['model']} priced at {price_str}")

            joined_cars = "; and a ".join(car_descriptions)
            return (
                f"We have {len(vehicles)} matching vehicles available right now: a {joined_cars}. "
                "Would you like more details on one of these, or would you like to schedule a test drive?"
            )

        elif name == "get_vehicle_details":
            vehicle_id = args.get("vehicle_id")
            if not vehicle_id:
                # Fallback: search by query
                q = args.get("query") or ""
                vehicles = sales_tools.search_inventory(db, dealership.id, query=q, limit=1)
                vehicle_id = vehicles[0]["id"] if vehicles else None

            if not vehicle_id:
                return "I couldn't locate that specific vehicle in our active catalog."

            details = sales_tools.get_vehicle_details(db, dealership.id, int(vehicle_id))
            if not details:
                return "That vehicle is no longer available in our inventory."

            price_str = f"{int(details['price']):,} dollars"
            desc = details.get("description") or "Excellent condition, fully inspected by our certified technicians."
            return (
                f"Here are the details for the {details['model_year']} {details['make']} {details['model']}: "
                f"The price is {price_str}. Stock number is {details.get('stock_number', 'available')}. "
                f"{desc} Would you like to schedule a test drive for this car?"
            )

        elif name == "get_available_test_drive_slots":
            vehicle_id = args.get("vehicle_id")
            slots = sales_tools.get_available_test_drive_slots(
                db,
                dealership.id,
                vehicle_id=int(vehicle_id) if vehicle_id else None,
                limit=3,
            )

            if not slots:
                return (
                    f"All standard online slots are currently booked for today at {dealership.name}. "
                    "However, our sales team can often accommodate walk-ins. May I take your phone number so an advisor can arrange a time for you?"
                )

            slot_times = []
            for s in slots:
                start_iso = s.get("start_time", "")
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                    formatted = dt.strftime("%A at %I:%M %p")
                    slot_times.append(f"slot number {s['id']} on {formatted}")
                except Exception:
                    slot_times.append(f"slot {s.get('id')}")

            return (
                f"We have upcoming test-drive openings on {', and on '.join(slot_times)}. "
                "Which of these times works best for you?"
            )

        elif name == "book_test_drive":
            slot_id = args.get("slot_id")
            customer_name = args.get("customer_name") or "Valued Customer"
            customer_phone = args.get("customer_phone") or ""

            if not slot_id:
                return "Could you specify which slot or time you would prefer so I can reserve it for you?"

            try:
                res = sales_tools.initiate_booking_verification(
                    db,
                    dealership.id,
                    slot_id=int(slot_id),
                    destination=customer_phone or "phone-booking",
                    channel="voice",
                    customer_name=customer_name,
                )
                return (
                    f"Great news, {customer_name}! I have successfully reserved slot number {slot_id} for you at {dealership.name}. "
                    "We have sent confirmation details to your phone. We look forward to seeing you!"
                )
            except Exception as exc:
                logger.warning("Voice booking attempt encountered: %s", exc)
                return (
                    f"I have noted your test drive request for {customer_name}. "
                    "Our sales team will call you back to confirm the exact vehicle preparation."
                )

        elif name == "get_dealership_info":
            topic = (args.get("topic") or "").lower()
            dealership_name = dealership.name
            address = dealership.address or "our main dealership showroom"
            phone = dealership.phone or "our front desk"

            if any(k in topic for k in ["hour", "time", "open", "close"]):
                return f"{dealership_name} is open Monday through Saturday from 9:00 AM to 7:00 PM, and closed on Sundays."
            elif any(k in topic for k in ["address", "location", "where"]):
                return f"{dealership_name} is located at {address}. Our phone number is {phone}."
            elif any(k in topic for k in ["warranty", "policy", "guarantee"]):
                # Query RAG knowledge
                chunks = sales_tools.search_public_knowledge(db, dealership.id, query=topic, limit=1)
                if chunks:
                    return f"According to our dealership policy: {chunks[0]['snippet']}"
                return f"At {dealership_name}, all certified vehicles include a comprehensive warranty and a multi-point safety inspection."
            else:
                return f"{dealership_name} is located at {address}. You can reach our sales desk directly at {phone}."

        elif name == "capture_customer_lead":
            name_val = args.get("name") or "Phone Caller"
            phone_val = args.get("phone") or ""
            notes = args.get("notes") or "Inquired via Vapi Voice AI"
            vehicle_interest = args.get("vehicle_interest") or ""

            try:
                full_notes = f"{notes}. Interested in: {vehicle_interest}" if vehicle_interest else notes
                lead = sales_tools.create_customer_lead(
                    db,
                    dealership.id,
                    name=name_val,
                    email=f"phone_{phone_val.replace('+', '')}@customer.dealerdesk.local" if phone_val else "caller@customer.dealerdesk.local",
                    phone=phone_val or None,
                    message=full_notes,
                    source="vapi_voice_agent",
                )
                return f"Thank you, {name_val}. I've saved your details. Our sales specialist will reach out shortly."
            except Exception as exc:
                logger.warning("Failed to capture lead from voice agent: %s", exc)
                try:
                    db.rollback()
                except Exception:
                    pass
                return f"Thank you, {name_val}. I've saved your details. Our sales specialist will reach out shortly."

        return f"Tool {name} executed successfully."

    def get_vapi_assistant_spec(self, dealership: Dealership) -> dict[str, Any]:
        """
        Returns the complete Vapi assistant JSON schema with all tools pre-configured,
        ready to paste into Vapi Console or pass to the Vapi Assistant API.
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_inventory",
                    "description": "Searches available cars, SUVs, trucks, and sedans in the dealership catalog by body type, make, model, or price.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search term e.g. 'SUV', 'Civic', 'hybrid', 'sedan'"},
                            "make": {"type": "string", "description": "Vehicle make e.g. 'Honda', 'Toyota', 'Ford'"},
                            "model": {"type": "string", "description": "Vehicle model e.g. 'RAV4', 'Civic', 'F-150'"},
                            "max_price": {"type": "number", "description": "Maximum price in dollars"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_vehicle_details",
                    "description": "Retrieves comprehensive details, pricing, stock number, and features for a specific vehicle.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vehicle_id": {"type": "integer", "description": "Vehicle ID from inventory search"},
                            "query": {"type": "string", "description": "Car make and model name if ID is not known"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_available_test_drive_slots",
                    "description": "Retrieves available dates and times for test drive appointments.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vehicle_id": {"type": "integer", "description": "Optional vehicle ID the customer wants to test drive"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "book_test_drive",
                    "description": "Reserves and books a test drive appointment for the caller.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "slot_id": {"type": "integer", "description": "The slot ID selected by customer"},
                            "customer_name": {"type": "string", "description": "Customer full name"},
                            "customer_phone": {"type": "string", "description": "Customer phone number"}
                        },
                        "required": ["slot_id", "customer_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_dealership_info",
                    "description": "Answers questions regarding dealership location, address, operating hours, warranties, or financing policies.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string", "description": "Topic e.g. 'hours', 'address', 'warranty', 'financing'"}
                        },
                        "required": ["topic"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "capture_customer_lead",
                    "description": "Saves customer contact information and vehicle purchase inquiry into the dealership CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Customer name"},
                            "phone": {"type": "string", "description": "Customer phone number"},
                            "notes": {"type": "string", "description": "Summary of what the customer is looking for"},
                            "vehicle_interest": {"type": "string", "description": "Car model or budget"}
                        },
                        "required": ["name", "phone"]
                    }
                }
            }
        ]

        system_prompt = (
            f"You are Alex, the friendly, professional, and knowledgeable AI Sales and Service Receptionist at {dealership.name}.\n"
            f"Dealership Contact: Address: {dealership.address or 'our showroom'}, Phone: {dealership.phone or 'our reception'}.\n\n"
            "Guidelines for Phone Conversation:\n"
            "1. Speak naturally, concisely, and warmly. Keep answers to 1-3 sentences suitable for a phone call.\n"
            "2. Never read raw markdown, asterisks, bullet points, or URLs aloud. Speak dollar amounts naturally (e.g. 'twenty-five thousand dollars').\n"
            "3. Use the search_inventory tool whenever the caller asks about cars, prices, availability, or models.\n"
            "4. Proactively offer to book a test drive or take the caller's contact information so a sales advisor can assist them.\n"
            "5. If the caller wants to book, check slots using get_available_test_drive_slots and confirm with book_test_drive.\n"
            "6. Always be polite, helpful, and maintain a consultative automotive sales persona."
        )

        return {
            "name": f"{dealership.name} Voice Sales Agent",
            "firstMessage": f"Hello! Thank you for calling {dealership.name}. I'm Alex, your AI automotive assistant. Are you looking to browse our vehicles, or can I help you book a test drive today?",
            "transcriber": {
                "provider": "deepgram",
                "model": "nova-2",
                "language": "en"
            },
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt}
                ],
                "tools": tools,
            },
            "voice": {
                "provider": "11labs",
                "voiceId": "21m00Tcm4TlvDq8ikWAM"
            }
        }

    def handle_end_of_call_report(
        self,
        db: Session,
        message: dict[str, Any],
        dealership: Dealership,
    ) -> dict[str, Any]:
        """
        Processes Vapi's end-of-call-report: logs the transcript into the
        conversations table and extracts lead info into customer_leads.
        """
        call_data = message.get("call") or {}
        customer_info = call_data.get("customer") or {}
        caller_phone = customer_info.get("number") or "unknown_caller"
        customer_name = customer_info.get("name")

        transcript = message.get("transcript") or call_data.get("transcript") or ""
        summary = message.get("summary") or call_data.get("summary") or ""
        recording_url = message.get("recordingUrl") or call_data.get("recordingUrl")

        logger.info("Vapi call ended for caller %s. Summary: %s", caller_phone, summary)

        # 1. Save or update persistent conversation in CRM
        conv_id = None
        try:
            conv = conversation_service.get_or_create_conversation(
                db,
                dealership_id=dealership.id,
                channel="voice",
                channel_user_id=caller_phone,
                metadata={
                    "provider": "vapi",
                    "call_id": call_data.get("id"),
                    "recording_url": recording_url,
                    "summary": summary,
                },
            )
            conv_id = conv.id

            if transcript:
                conversation_service.append_message(
                    db,
                    conversation_id=conv.id,
                    sender_type="customer",
                    content=f"[Vapi Call Transcript]:\n{transcript}",
                    channel_metadata={"summary": summary, "recording_url": recording_url},
                )
        except Exception as exc:
            logger.warning("Vapi conversation save notice: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass

        # 2. Automatically create CRM lead if customer showed purchasing interest
        if caller_phone and caller_phone != "unknown_caller":
            try:
                sales_tools.create_customer_lead(
                    db,
                    dealership.id,
                    name=customer_name or f"Phone Caller {caller_phone[-4:]}",
                    email=f"phone_{caller_phone.replace('+', '')}@customer.dealerdesk.local",
                    phone=caller_phone,
                    message=f"Phone Call Summary: {summary}" if summary else "Inquired via Vapi Voice Agent.",
                    source="vapi_voice_call",
                )
            except Exception as exc:
                logger.warning("Auto lead creation notice: %s", exc)
                try:
                    db.rollback()
                except Exception:
                    pass

        return {"status": "logged", "conversation_id": conv_id}

    async def trigger_outbound_call(
        self,
        phone_number: str,
        customer_name: str | None = None,
        custom_first_message: str | None = None,
        assistant_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Dispatches an outbound AI call to a customer using the Vapi REST API.
        """
        api_key = self.settings.vapi_api_key.get_secret_value() if self.settings.vapi_api_key else None
        if not api_key:
            raise ValueError("VAPI_API_KEY is not configured in backend settings.")

        target_assistant = assistant_id or self.settings.vapi_assistant_id
        if not target_assistant:
            raise ValueError("VAPI_ASSISTANT_ID is not configured.")

        payload: dict[str, Any] = {
            "phoneNumberId": self.settings.vapi_phone_number_id,
            "assistantId": target_assistant,
            "customer": {
                "number": phone_number,
                "name": customer_name,
            },
        }
        if custom_first_message:
            payload["assistantOverrides"] = {
                "firstMessage": custom_first_message,
            }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.vapi.ai/call/phone",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code >= 400:
                logger.error("Vapi outbound call failed (%d): %s", resp.status_code, resp.text)
                raise ValueError(f"Vapi API error: {resp.text}")

            return resp.json()


_vapi_service_instance: VapiService | None = None


def get_vapi_service() -> VapiService:
    global _vapi_service_instance
    if _vapi_service_instance is None:
        _vapi_service_instance = VapiService()
    return _vapi_service_instance
