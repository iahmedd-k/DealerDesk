import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.channels.vapi.schemas import VapiServerMessage, VapiWebhookPayload
from app.channels.vapi.service import get_vapi_service

pytestmark = pytest.mark.no_db

client = TestClient(app)


def test_vapi_webhook_health_check():
    """Verify Vapi webhook GET health check."""
    response = client.get("/api/v1/channels/vapi/webhook")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["channel"] == "voice"
    assert data["provider"] == "vapi"


def test_vapi_assistant_request_event():
    """Verify Vapi assistant-request event returns full assistant configuration."""
    payload = {
        "message": {
            "type": "assistant-request",
            "call": {
                "id": "vapi_call_test_01",
                "customer": {"number": "+14155552671", "name": "Sarah Connor"},
            },
        }
    }
    response = client.post("/api/v1/channels/vapi/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "assistant" in data
    assistant = data["assistant"]
    assert "model" in assistant
    assert "firstMessage" in assistant
    assert len(assistant["model"]["tools"]) >= 5


def test_vapi_tool_calls_inventory_and_info():
    """Verify Vapi tool-calls event executes tools and returns voice-friendly output."""
    payload = {
        "message": {
            "type": "tool-calls",
            "call": {
                "id": "vapi_call_test_02",
                "customer": {"number": "+14155552671"},
            },
            "toolCalls": [
                {
                    "id": "call_inv_01",
                    "type": "function",
                    "function": {
                        "name": "search_inventory",
                        "arguments": {"query": "SUV", "max_price": 40000},
                    },
                },
                {
                    "id": "call_info_02",
                    "type": "function",
                    "function": {
                        "name": "get_dealership_info",
                        "arguments": {"topic": "hours"},
                    },
                },
            ],
        }
    }
    response = client.post("/api/v1/channels/vapi/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    results = data["results"]
    assert len(results) == 2
    assert results[0]["toolCallId"] == "call_inv_01"
    assert isinstance(results[0]["result"], str)
    assert results[1]["toolCallId"] == "call_info_02"
    assert "open" in results[1]["result"].lower() or "monday" in results[1]["result"].lower()


def test_vapi_tool_calls_lead_capture():
    """Verify capture_customer_lead tool saves lead info."""
    payload = {
        "message": {
            "type": "tool-calls",
            "toolCalls": [
                {
                    "id": "call_lead_01",
                    "type": "function",
                    "function": {
                        "name": "capture_customer_lead",
                        "arguments": {
                            "name": "John Doe",
                            "phone": "+14155559876",
                            "notes": "Looking for financing options on pre-owned sedan",
                            "vehicle_interest": "Honda Civic",
                        },
                    },
                }
            ],
        }
    }
    response = client.post("/api/v1/channels/vapi/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1
    assert "John Doe" in data["results"][0]["result"]


def test_vapi_end_of_call_report():
    """Verify end-of-call-report is received and logged without errors."""
    payload = {
        "message": {
            "type": "end-of-call-report",
            "call": {
                "id": "vapi_call_test_03",
                "customer": {"number": "+14155551234", "name": "Alice"},
            },
            "transcript": "Hello, I am interested in testing a car tomorrow. That sounds great, thank you!",
            "summary": "Customer Alice called to inquire about test drive availability.",
            "recordingUrl": "https://vapi-recordings.s3.amazonaws.com/call_03.wav",
        }
    }
    response = client.post("/api/v1/channels/vapi/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_vapi_assistant_spec_endpoint():
    """Verify GET /assistant-spec endpoint returns full exportable schema."""
    response = client.get("/api/v1/channels/vapi/assistant-spec")
    assert response.status_code == 200
    spec = response.json()
    assert "name" in spec
    assert "firstMessage" in spec
    assert "model" in spec
    assert "tools" in spec["model"]
