import asyncio
import json
import logging
import re
from typing import Any, AsyncIterator

import httpx

from app.core.config import get_settings
from app.core.errors import BadGatewayError, ServiceUnavailableError
from app.core.safety import sanitize_output

logger = logging.getLogger("dealerdesk.llm")


def generate_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 800,
    context_data: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    llm_cfg = settings.get_llm_config()
    if llm_cfg is not None:
        llm_url, llm_key, llm_model, _ = llm_cfg
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.post(
                    llm_url,
                    json={
                        "model": llm_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    headers={
                        "Authorization": f"Bearer {llm_key}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            logger.error("Language model request failed: %s", exc)
            raise ServiceUnavailableError("The language model is temporarily unavailable") from exc
        if response.status_code != 200:
            logger.error("Language model returned HTTP status %d", response.status_code)
            raise BadGatewayError("The language model could not complete the request")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise BadGatewayError("The language model returned an invalid response") from exc
        if not isinstance(content, str) or not content.strip():
            raise BadGatewayError("The language model returned an empty response")
        dealership_name = (context_data or {}).get("dealership_name", "the dealership")
        return sanitize_output(content.strip(), dealership_name=dealership_name)

    # Local synthesis is the intentional mode when no remote provider is configured.
    raw_response = _synthesize_grounded_response(messages, context_data or {})
    dealership_name = (context_data or {}).get("dealership_name", "the dealership")
    return sanitize_output(raw_response, dealership_name=dealership_name)


async def stream_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 800,
    context_data: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """
    Asynchronously streams tokens or phrases from external LLM or local synthesis engine.
    """
    settings = get_settings()
    llm_cfg = settings.get_llm_config()
    if llm_cfg is not None:
        llm_url, llm_key, llm_model, _ = llm_cfg
        content_parts: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    llm_url,
                    json={
                        "model": llm_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True,
                    },
                    headers={
                        "Authorization": f"Bearer {llm_key}",
                        "Content-Type": "application/json",
                    },
                ) as response:
                    if response.status_code != 200:
                        logger.error("Streaming language model returned HTTP status %d", response.status_code)
                        raise BadGatewayError("The language model could not complete the request")
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            event = json.loads(data)
                            delta = event["choices"][0]["delta"].get("content", "")
                        except (ValueError, KeyError, IndexError, TypeError) as exc:
                            raise BadGatewayError(
                                "The language model returned an invalid streaming response"
                            ) from exc
                        if delta:
                            if not isinstance(delta, str):
                                raise BadGatewayError(
                                    "The language model returned an invalid streaming response"
                                )
                            content_parts.append(delta)
        except httpx.HTTPError as exc:
            logger.error("Streaming language model request failed: %s", exc)
            raise ServiceUnavailableError("The language model is temporarily unavailable") from exc
        if not content_parts:
            raise BadGatewayError("The language model returned an empty response")
        safe_content = sanitize_output(
            "".join(content_parts),
            dealership_name=(context_data or {}).get("dealership_name", "the dealership"),
        )
        for token in re.split(r"(\s+)", safe_content):
            if token:
                yield token
                await asyncio.sleep(0.012)
        return

    full_text = generate_completion(messages, temperature=temperature, max_tokens=max_tokens, context_data=context_data)
    # Split by words preserving punctuation
    tokens = re.split(r"(\s+)", full_text)
    for token in tokens:
        if token:
            yield token
            await asyncio.sleep(0.012)


def _synthesize_grounded_response(
    messages: list[dict[str, str]],
    context_data: dict[str, Any],
) -> str:
    dealership_name = context_data.get("dealership_name", "the dealership")
    hours = context_data.get("business_hours")
    vehicles = context_data.get("vehicles", [])
    slots = context_data.get("slots", [])
    chunks = context_data.get("knowledge_chunks", [])
    intent = context_data.get("intent", "general")

    if intent == "human_handoff":
        phone = context_data.get("phone")
        contact = f" You can reach the dealership at **{phone}**." if phone else ""
        return f"I can't connect you to a representative from this chat.{contact}"

    if intent == "test_drive_booking":
        if slots:
            slot_times = [
                f"* **Slot #{slot.get('id') or slot.get('slot_id')}**: {slot['starts_at'][:16].replace('T', ' ')} UTC "
                f"({slot['remaining_capacity']} spot{'s' if slot['remaining_capacity'] != 1 else ''} open)"
                for slot in slots[:3]
            ]
            return (
                f"Available test-drive slots at **{dealership_name}**:\n\n"
                + "\n".join(slot_times)
                + "\n\nSelect a slot in the test-drive schedule to complete a booking."
            )
        return "No test drive slots are currently available in the schedule."

    if intent == "inventory_inquiry":
        if vehicles:
            lines = [
                f"* **{vehicle['model_year']} {vehicle['make']} {vehicle['model']}** — "
                f"**${vehicle['price']:,.2f}** (Stock #{vehicle['stock_number']})"
                for vehicle in vehicles[:4]
            ]
            return f"Currently available vehicles at **{dealership_name}**:\n\n" + "\n".join(lines)
        return "No matching vehicles are listed in the current available inventory."

    if chunks:
        excerpt = chunks[0]["snippet"].strip().strip('"')
        source = chunks[0].get("filename", "indexed document")
        page = chunks[0].get("page_number")
        citation = f" — {source}" + (f", page {page}" if page is not None else "")
        return f"{excerpt}\n\nSource: {citation}"

    if intent == "dealership_info":
        details = []
        if context_data.get("address"):
            details.append(f"Address: {context_data['address']}")
        if hours:
            details.append(f"Business hours: {hours}")
        if context_data.get("phone"):
            details.append(f"Phone: {context_data['phone']}")
        if details:
            return f"**{dealership_name}**\n\n" + "\n".join(f"- {detail}" for detail in details)
        return f"Contact details and business hours for **{dealership_name}** are not configured."

    return (
        f"I can help with **{dealership_name}**'s listed inventory, available test-drive slots, "
        "dealership details, and indexed documents."
    )
