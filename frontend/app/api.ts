import {
  AuditLogItem,
  Brand,
  Dealership,
  HealthStatus,
  KnowledgeDocument,
  MOCK_AUDIT_LOGS,
  MOCK_BOOKINGS,
  MOCK_BRANDS,
  MOCK_DEALERSHIP,
  MOCK_DEALERSHIPS,
  MOCK_HEALTH,
  MOCK_INVITATIONS,
  MOCK_KNOWLEDGE_DOCUMENTS,
  MOCK_STAFF,
  MOCK_TEST_DRIVE_SLOTS,
  MOCK_VEHICLES,
  StaffInvitation,
  StaffUser,
  TestDriveBooking,
  TestDriveSlot,
  Vehicle,
} from "./lib/mockData";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  errorCode?: string;
  requestId?: string;
  statusCode: number;

  constructor(message: string, statusCode: number, errorCode?: string, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.errorCode = errorCode;
    this.requestId = requestId;
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  // Correlation ID tracing
  if (!headers.has("X-Request-ID")) {
    headers.set("X-Request-ID", `fe-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`);
  }

  // Idempotency for mutating requests
  const method = (options.method ?? "GET").toUpperCase();
  if (["POST", "PUT", "PATCH"].includes(method) && !headers.has("Idempotency-Key")) {
    headers.set("Idempotency-Key", `idem-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`);
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      let errorCode: string | undefined;
      let requestId = response.headers.get("X-Request-ID") || undefined;

      try {
        const body = (await response.json()) as {
          detail?: string | string[];
          error_code?: string;
          request_id?: string;
        };
        if (Array.isArray(body.detail)) {
          detail = body.detail.join(", ");
        } else if (typeof body.detail === "string") {
          detail = body.detail;
        }
        errorCode = body.error_code;
        if (body.request_id) requestId = body.request_id;
      } catch {
        // Fallback to response status text
      }

      throw new ApiError(detail, response.status, errorCode, requestId);
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return response.json();
  } catch (error) {
    // If it's already an ApiError with HTTP response, rethrow
    if (error instanceof ApiError) {
      throw error;
    }
    // Network failure / offline backend fallback
    console.warn(`[DealerDesk ERP] Network fetch to ${path} failed, falling back to static ERP dataset:`, error);
    return getFallbackData<T>(path, options);
  }
}

// Fallback provider for static standalone operation
function getFallbackData<T>(path: string, options: RequestInit): T {
  const method = (options.method ?? "GET").toUpperCase();

  // Public Dealerships
  if (path.includes("/dealerships/public") || path === "/dealerships") {
    return MOCK_DEALERSHIPS as T;
  }
  if (path.match(/\/dealerships\/\d+$/)) {
    return MOCK_DEALERSHIP as T;
  }

  // Vehicles
  if (path.includes("/vehicles/public") || path.includes("/vehicles")) {
    return MOCK_VEHICLES as T;
  }

  // Brands
  if (path.includes("/brands")) {
    return MOCK_BRANDS as T;
  }

  // Test Drive Slots
  if (path.includes("/test-drive-slots") && !path.includes("/bookings")) {
    return MOCK_TEST_DRIVE_SLOTS as T;
  }

  // Test Drive Bookings
  if (path.includes("/test-drive-bookings") || path.includes("/bookings")) {
    if (method === "POST") {
      const newBooking: TestDriveBooking = {
        id: Math.floor(Math.random() * 9000) + 1000,
        slot_id: 201,
        dealership_id: 1,
        vehicle_id: 101,
        vehicle_name: "2024 Toyota Camry XSE",
        customer_id: 501,
        customer_name: "Demo Customer",
        customer_email: "customer@demo.com",
        customer_phone: "+1-212-555-0322",
        status: "booked",
        created_at: new Date().toISOString(),
        cancelled_at: null,
      };
      return newBooking as T;
    }
    return MOCK_BOOKINGS as T;
  }

  // Knowledge documents
  if (path.includes("/knowledge/documents")) {
    return MOCK_KNOWLEDGE_DOCUMENTS as T;
  }

  // Staff & Invitations
  if (path.includes("/staff/invitations")) {
    return MOCK_INVITATIONS as T;
  }
  if (path.includes("/staff")) {
    return MOCK_STAFF as T;
  }

  // Audit Logs
  if (path.includes("/audit-logs")) {
    return {
      items: MOCK_AUDIT_LOGS,
      total: MOCK_AUDIT_LOGS.length,
      page: 1,
      page_size: 50,
    } as T;
  }

  // Health
  if (path.includes("/health")) {
    return MOCK_HEALTH as T;
  }

  // AI Assistant Chat
  if (path.includes("/assistant/chat")) {
    const body = options.body ? JSON.parse(options.body as string) : {};
    const message = (body.message || "").toLowerCase();
    let reply = `Welcome to Apex Motors NYC! We are an authorized dealership located at 450 W 33rd St, New York. How can I assist you with our inventory or test-drives today?`;
    let intent = "general";
    const sources = [{ source: "Dealership Profile", detail: "Apex Motors NYC (450 W 33rd St, New York)" }];

    if (message.includes("camry") || message.includes("toyota")) {
      reply = `We have the 2024 Toyota Camry XSE (Stock: STK-2024-001) in stock for $36,800. It features a sport-tuned suspension, dual exhaust, panoramic glass roof, and Toyota Safety Sense. It is currently available and ready for a test drive!`;
      intent = "inventory_inquiry";
      sources.push({ source: "Dealership Inventory", detail: "2024 Toyota Camry XSE (STK-2024-001)" });
    } else if (message.includes("bmw") || message.includes("m4")) {
      reply = `Our 2024 BMW M4 Competition Coupe xDrive (Stock: STK-2024-002) is available for $86,400 with a 503 hp TwinPower Turbo engine and Executive Package.`;
      intent = "inventory_inquiry";
      sources.push({ source: "Dealership Inventory", detail: "2024 BMW M4 Competition (STK-2024-002)" });
    } else if (message.includes("test drive") || message.includes("slot") || message.includes("book")) {
      reply = `Test drives are currently available Monday through Saturday. You can book an immediate slot for the 2024 Toyota Camry or 2024 BMW M4 Competition online with instant confirmation.`;
      intent = "test_drive_booking";
      sources.push({ source: "Test Drive Schedule", detail: "Upcoming slots with remaining capacity" });
    } else if (message.includes("hour") || message.includes("address") || message.includes("location") || message.includes("time")) {
      reply = `Apex Motors NYC is open Monday to Friday 09:00 - 18:00, and Saturday 10:00 - 17:00. We are located at 450 W 33rd St, New York, NY 10001. Contact: +1-212-555-0199.`;
      intent = "dealership_info";
      sources.push({ source: "Operating Hours & Policy", detail: "Mon-Sat business hours" });
    } else if (message.includes("warranty") || message.includes("policy") || message.includes("terms")) {
      reply = `All certified vehicles include the standard 3-year/36,000-mile bumper-to-bumper and 5-year/60,000-mile powertrain coverage. Comprehensive vehicle documentation is stored in our knowledge base.`;
      intent = "policy_inquiry";
      sources.push({ source: "Knowledge Base", detail: "Toyota 2024 Camry Specs & Warranty Guide.pdf" });
    }

    return {
      dealership_id: 1,
      dealership_name: "Apex Motors NYC",
      response: reply,
      intent,
      sources,
      session_id: body.session_id || "demo-session-123",
      timestamp: new Date().toISOString(),
    } as T;
  }

  return {} as T;
}
