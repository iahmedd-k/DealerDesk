from typing import Any
from pydantic import BaseModel, Field


class VapiCustomer(BaseModel):
    number: str | None = Field(default=None, description="Customer phone number in E.164 format")
    name: str | None = Field(default=None, description="Customer name if known")


class VapiCall(BaseModel):
    id: str | None = Field(default=None, description="Unique Vapi call ID")
    status: str | None = Field(default=None, description="Call status e.g. queued, ringing, in-progress, ended")
    customer: VapiCustomer | None = Field(default=None, description="Caller information")
    phone_number_id: str | None = Field(default=None, alias="phoneNumberId")
    assistant_id: str | None = Field(default=None, alias="assistantId")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class VapiFunctionCall(BaseModel):
    name: str = Field(..., description="Function name to invoke")
    arguments: dict[str, Any] | str = Field(default_factory=dict, description="Parameters passed by LLM")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class VapiToolCall(BaseModel):
    id: str = Field(..., description="Tool call identifier")
    type: str = Field(default="function", description="Type of tool")
    function: VapiFunctionCall = Field(..., description="Function invocation payload")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class VapiServerMessage(BaseModel):
    """
    Standard message envelope received from Vapi server webhooks.
    """
    type: str = Field(..., description="Event type: assistant-request, tool-calls, function-call, end-of-call-report, status-update, transcript")
    call: VapiCall | None = Field(default=None, description="Active call metadata")
    tool_calls: list[VapiToolCall] | None = Field(default=None, alias="toolCalls")
    tool_call_list: list[VapiToolCall] | None = Field(default=None, alias="toolCallList")
    function_call: VapiFunctionCall | None = Field(default=None, alias="functionCall")
    transcript: str | None = Field(default=None, description="Transcribed audio text")
    summary: str | None = Field(default=None, description="AI summary of the completed call")
    recording_url: str | None = Field(default=None, alias="recordingUrl")
    ended_reason: str | None = Field(default=None, alias="endedReason")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class VapiWebhookPayload(BaseModel):
    message: VapiServerMessage = Field(..., description="Vapi event container")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class VapiToolResult(BaseModel):
    toolCallId: str
    result: Any


class VapiToolResponse(BaseModel):
    results: list[VapiToolResult]


class VapiOutboundCallRequest(BaseModel):
    phone_number: str = Field(..., description="Recipient phone number in E.164 format, e.g., +14155552671")
    customer_name: str | None = Field(default=None, description="Customer full name")
    dealership_id: int | None = Field(default=None, description="Target dealership ID (defaults to primary active dealership)")
    assistant_id: str | None = Field(default=None, description="Optional Vapi assistant ID override")
    custom_first_message: str | None = Field(default=None, description="Optional custom first greeting spoken by the voice agent")
