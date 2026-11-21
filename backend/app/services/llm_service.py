import logging
from typing import Any
import httpx

from app.core.config import get_settings

logger = logging.getLogger("dealerdesk.llm")


def generate_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 800,
    context_data: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()

    # 1. External LLM Provider (OpenAI, Groq, Ollama, Gemini compatible endpoint)
    if settings.llm_api_url and settings.llm_api_key:
        try:
            headers = {
                "Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": settings.llm_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.post(settings.llm_api_url, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0]["message"]["content"].strip()
                logger.warning(
                    "Remote LLM request returned status %d: %s",
                    res.status_code,
                    res.text[:200],
                )
        except Exception as exc:
            logger.warning("Remote LLM connection failed: %s. Using local synthesis engine.", exc)

    # 2. Local Grounded Synthesis Engine (Guarantees reliable operation)
    return _synthesize_grounded_response(messages, context_data or {})


def _synthesize_grounded_response(
    messages: list[dict[str, str]],
    context_data: dict[str, Any],
) -> str:
    user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_query = msg.get("content", "").lower()
            break

    dealership_name = context_data.get("dealership_name", "DealerDesk")
    hours = context_data.get("business_hours", "09:00 - 17:00")
    vehicles = context_data.get("vehicles", [])
    slots = context_data.get("slots", [])
    chunks = context_data.get("knowledge_chunks", [])
    intent = context_data.get("intent", "general")

    # Intent: Test Drive Booking / Availability
    if intent == "test_drive_booking" or any(k in user_query for k in ["test drive", "drive", "slot", "appointment", "book"]):
        if slots:
            slot_times = [
                f"- Slot #{s['id']}: {s['starts_at'][:16].replace('T', ' ')} (Available capacity: {s['remaining_capacity']})"
                for s in slots[:3]
            ]
            slots_text = "\n".join(slot_times)
            return (
                f"Welcome to {dealership_name}! We currently have test-drive slots available for you:\n\n"
                f"{slots_text}\n\n"
                "Would you like to book one of these slots? To confirm, you can proceed with your preferred slot and contact details."
            )
        return (
            f"At {dealership_name}, test drives are conducted during our business hours ({hours}). "
            "There are currently no open slots generated for that exact window, but our team can schedule one for you shortly."
        )

    # Intent: Inventory / Vehicle Lookup
    if intent == "inventory_inquiry" or any(k in user_query for k in ["car", "vehicle", "price", "inventory", "stock", "model", "buy"]):
        if vehicles:
            lines = [
                f"- {v['model_year']} {v['make']} {v['model']} (${v['price']:,.2f}) - Stock #{v['stock_number']}"
                for v in vehicles[:4]
            ]
            veh_text = "\n".join(lines)
            return (
                f"Here are the current vehicles available at {dealership_name}:\n\n"
                f"{veh_text}\n\n"
                "All of these units are in stock and ready for inspection. Would you like to schedule a test drive for one of them?"
            )
        return f"We currently don't have matching vehicles in our online stock at {dealership_name}, but new inventory arrives weekly. Let us know what model you are looking for!"

    # Intent: Knowledge / Documentation
    if chunks:
        passage = chunks[0]["snippet"]
        return (
            f"According to {dealership_name}'s official dealership documentation:\n\n"
            f"\"{passage}\"\n\n"
            f"Please let me know if you would like more information or if you'd like to book an appointment with our sales specialists."
        )

    # Intent: Dealership Information / Hours
    if any(k in user_query for k in ["hour", "location", "open", "address", "phone", "time"]):
        address = context_data.get("address", "our dealership location")
        phone = context_data.get("phone", "our front desk")
        return (
            f"{dealership_name} is located at {address}. Our operating hours are {hours}. "
            f"You can reach our team at {phone}. How can we assist you today?"
        )

    # Default friendly greeting / inquiry
    return (
        f"Hello! I am the AI assistant for {dealership_name}. "
        "I can help you browse our vehicle inventory, answer questions from our dealership guides, "
        "or book an available test-drive slot. How can I help you today?"
    )
