export interface Dealership {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  address: string | null;
  timezone: string;
  is_active: boolean;
}

export interface Brand {
  id: number;
  dealership_id: number;
  name: string;
  logo_url: string | null;
  is_active: boolean;
  is_deleted: boolean;
}

export interface VehicleImage {
  id: number;
  vehicle_id: number;
  public_url: string;
  media_type: string;
  alt_text: string | null;
  position: number;
}

export interface Vehicle {
  id: number;
  dealership_id: number;
  brand_id: number;
  make: string;
  model: string;
  model_year: number;
  variant: string | null;
  description: string | null;
  price: number;
  stock_number: string;
  is_available: boolean;
  test_drive_enabled: boolean;
  images?: VehicleImage[];
}

export interface TestDriveSlot {
  id: number;
  vehicle_id: number;
  starts_at: string;
  ends_at: string;
  capacity: number;
  booked_count: number;
  is_active: boolean;
  remaining_capacity?: number;
  is_available?: boolean;
}

export interface TestDriveBooking {
  id: number;
  slot_id: number;
  dealership_id: number;
  vehicle_id: number;
  vehicle_name?: string;
  customer_id: number;
  customer_name?: string;
  customer_email?: string;
  customer_phone?: string;
  status: "booked" | "completed" | "cancelled";
  created_at: string;
  cancelled_at: string | null;
  starts_at?: string;
  ends_at?: string;
}

export interface KnowledgeDocument {
  id: number;
  dealership_id: number;
  brand_id: number | null;
  brand_name?: string | null;
  title: string;
  mime_type: string;
  source_file: string;
  chunk_count: number;
  created_at: string;
  status: "ready" | "indexing";
}

export interface StaffUser {
  id: number;
  dealership_id: number;
  name: string;
  email: string;
  role: "dealership_admin" | "manager" | "sales_rep" | "dealerdesk_admin";
  is_active: boolean;
  last_login?: string;
}

export interface StaffInvitation {
  id: number;
  dealership_id: number;
  name: string;
  email: string;
  role: string;
  expires_at: string;
  delivery_status: string;
  status: string;
}

export interface AuditLogItem {
  id: number;
  dealership_id: number;
  actor_id: number | null;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id: string;
  ip_address: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface HealthStatus {
  status: "ok" | "degraded";
  db_latency_ms: number;
  database: string;
  services: {
    storage: string;
    email: string;
    embeddings: string;
    llm: string;
  };
}

export const MOCK_DEALERSHIP: Dealership = {
  id: 1,
  name: "Apex Motors NYC",
  email: "contact@apexmotors.com",
  phone: "+1-212-555-0199",
  address: "450 W 33rd St, New York, NY 10001",
  timezone: "America/New_York",
  is_active: true,
};

export const MOCK_DEALERSHIPS: Dealership[] = [
  MOCK_DEALERSHIP,
  {
    id: 2,
    name: "Apex Motors Downtown",
    email: "downtown@apexmotors.com",
    phone: "+1-212-555-0144",
    address: "180 Broadway, New York, NY 10038",
    timezone: "America/New_York",
    is_active: true,
  },
  {
    id: 3,
    name: "Summit Prestige Auto",
    email: "info@summitprestige.com",
    phone: "+1-312-555-8820",
    address: "600 N Michigan Ave, Chicago, IL 60611",
    timezone: "America/Chicago",
    is_active: true,
  },
];

export const MOCK_BRANDS: Brand[] = [
  { id: 1, dealership_id: 1, name: "Toyota", logo_url: "https://images.unsplash.com/photo-1617814076367-b759c7d7e738?auto=format&fit=crop&w=120&q=80", is_active: true, is_deleted: false },
  { id: 2, dealership_id: 1, name: "BMW", logo_url: "https://images.unsplash.com/photo-1555215695-3004980ad54e?auto=format&fit=crop&w=120&q=80", is_active: true, is_deleted: false },
  { id: 3, dealership_id: 1, name: "Audi", logo_url: "https://images.unsplash.com/photo-1603584173870-7f23fdae1b7a?auto=format&fit=crop&w=120&q=80", is_active: true, is_deleted: false },
  { id: 4, dealership_id: 1, name: "Porsche", logo_url: "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=120&q=80", is_active: true, is_deleted: false },
];

export const MOCK_VEHICLES: Vehicle[] = [
  {
    id: 101,
    dealership_id: 1,
    brand_id: 1,
    make: "Toyota",
    model: "Camry",
    model_year: 2024,
    variant: "XSE V6",
    description: "Sport-tuned suspension, dual exhaust, panoramic glass roof, 9-inch multimedia display, Toyota Safety Sense 2.5+.",
    price: 36800,
    stock_number: "STK-2024-001",
    is_available: true,
    test_drive_enabled: true,
    images: [
      { id: 1, vehicle_id: 101, public_url: "https://images.unsplash.com/photo-1621007947382-bb3c3994e3fb?auto=format&fit=crop&w=800&q=80", media_type: "image/jpeg", alt_text: "Front angle 2024 Toyota Camry", position: 0 },
      { id: 2, vehicle_id: 101, public_url: "https://images.unsplash.com/photo-1590362891991-f776e747a588?auto=format&fit=crop&w=800&q=80", media_type: "image/jpeg", alt_text: "Interior cockpit", position: 1 },
    ],
  },
  {
    id: 102,
    dealership_id: 1,
    brand_id: 2,
    make: "BMW",
    model: "M4 Competition",
    model_year: 2024,
    variant: "Coupe xDrive",
    description: "503 hp TwinPower Turbo inline 6-cylinder, carbon fiber roof, M Sport differential, executive package.",
    price: 86400,
    stock_number: "STK-2024-002",
    is_available: true,
    test_drive_enabled: true,
    images: [
      { id: 3, vehicle_id: 102, public_url: "https://images.unsplash.com/photo-1580273916550-e323be2ae537?auto=format&fit=crop&w=800&q=80", media_type: "image/jpeg", alt_text: "BMW M4 Competition front", position: 0 },
    ],
  },
  {
    id: 103,
    dealership_id: 1,
    brand_id: 3,
    make: "Audi",
    model: "RS6 Avant",
    model_year: 2024,
    variant: "Performance 4.0T",
    description: "621 hp twin-turbo V8, quattro all-wheel drive, ceramic brakes, dynamic ride control, sport exhaust.",
    price: 125800,
    stock_number: "STK-2024-003",
    is_available: true,
    test_drive_enabled: true,
    images: [
      { id: 4, vehicle_id: 103, public_url: "https://images.unsplash.com/photo-1603584173870-7f23fdae1b7a?auto=format&fit=crop&w=800&q=80", media_type: "image/jpeg", alt_text: "Audi RS6 Avant front quarter", position: 0 },
    ],
  },
  {
    id: 104,
    dealership_id: 1,
    brand_id: 4,
    make: "Porsche",
    model: "911 Carrera S",
    model_year: 2024,
    variant: "Coupe PDK",
    description: "443 hp twin-turbo 3.0L flat-6, Sport Chrono package, PASM sport suspension, BOSE surround audio.",
    price: 134200,
    stock_number: "STK-2024-004",
    is_available: true,
    test_drive_enabled: true,
    images: [
      { id: 5, vehicle_id: 104, public_url: "https://images.unsplash.com/photo-1614162692292-7ac56d7f7f1e?auto=format&fit=crop&w=800&q=80", media_type: "image/jpeg", alt_text: "Porsche 911 Carrera S", position: 0 },
    ],
  },
  {
    id: 105,
    dealership_id: 1,
    brand_id: 1,
    make: "Toyota",
    model: "RAV4 Hybrid",
    model_year: 2024,
    variant: "Limited AWD",
    description: "Electronic on-demand AWD, 40 MPG combined, SofTex-trimmed seats, digital rearview mirror.",
    price: 41250,
    stock_number: "STK-2024-005",
    is_available: false,
    test_drive_enabled: false,
    images: [
      { id: 6, vehicle_id: 105, public_url: "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=800&q=80", media_type: "image/jpeg", alt_text: "Toyota RAV4 Hybrid", position: 0 },
    ],
  },
  {
    id: 106,
    dealership_id: 1,
    brand_id: 2,
    make: "BMW",
    model: "i4 M50",
    model_year: 2024,
    variant: "Gran Coupe Electric",
    description: "Dual electric motors with 536 hp, 271-mile EPA range, curved display, adaptive M suspension.",
    price: 69700,
    stock_number: "STK-2024-006",
    is_available: true,
    test_drive_enabled: true,
    images: [
      { id: 7, vehicle_id: 106, public_url: "https://images.unsplash.com/photo-1555215695-3004980ad54e?auto=format&fit=crop&w=800&q=80", media_type: "image/jpeg", alt_text: "BMW i4 M50 Electric", position: 0 },
    ],
  },
];

const now = new Date();
function formatSlotTime(hoursAhead: number, durationMinutes: number = 45): { starts_at: string; ends_at: string } {
  const start = new Date(now.getTime() + hoursAhead * 60 * 60 * 1000);
  start.setMinutes(0, 0, 0);
  const end = new Date(start.getTime() + durationMinutes * 60 * 1000);
  return {
    starts_at: start.toISOString(),
    ends_at: end.toISOString(),
  };
}

export const MOCK_TEST_DRIVE_SLOTS: TestDriveSlot[] = [
  {
    id: 201,
    vehicle_id: 101,
    ...formatSlotTime(4),
    capacity: 2,
    booked_count: 1,
    is_active: true,
    remaining_capacity: 1,
    is_available: true,
  },
  {
    id: 202,
    vehicle_id: 101,
    ...formatSlotTime(6),
    capacity: 2,
    booked_count: 0,
    is_active: true,
    remaining_capacity: 2,
    is_available: true,
  },
  {
    id: 203,
    vehicle_id: 102,
    ...formatSlotTime(24),
    capacity: 1,
    booked_count: 1,
    is_active: true,
    remaining_capacity: 0,
    is_available: false,
  },
  {
    id: 204,
    vehicle_id: 102,
    ...formatSlotTime(27),
    capacity: 1,
    booked_count: 0,
    is_active: true,
    remaining_capacity: 1,
    is_available: true,
  },
  {
    id: 205,
    vehicle_id: 103,
    ...formatSlotTime(48),
    capacity: 2,
    booked_count: 0,
    is_active: true,
    remaining_capacity: 2,
    is_available: true,
  },
  {
    id: 206,
    vehicle_id: 104,
    ...formatSlotTime(52),
    capacity: 1,
    booked_count: 0,
    is_active: true,
    remaining_capacity: 1,
    is_available: true,
  },
];

export const MOCK_BOOKINGS: TestDriveBooking[] = [
  {
    id: 301,
    slot_id: 201,
    dealership_id: 1,
    vehicle_id: 101,
    vehicle_name: "2024 Toyota Camry XSE",
    customer_id: 501,
    customer_name: "Sophia Martinez",
    customer_email: "sophia.m@example.com",
    customer_phone: "+1-212-555-0322",
    status: "booked",
    created_at: new Date(now.getTime() - 24 * 3600 * 1000).toISOString(),
    cancelled_at: null,
    starts_at: MOCK_TEST_DRIVE_SLOTS[0].starts_at,
    ends_at: MOCK_TEST_DRIVE_SLOTS[0].ends_at,
  },
  {
    id: 302,
    slot_id: 203,
    dealership_id: 1,
    vehicle_id: 102,
    vehicle_name: "2024 BMW M4 Competition",
    customer_id: 502,
    customer_name: "Liam Chen",
    customer_email: "liam.chen@example.com",
    customer_phone: "+1-212-555-0488",
    status: "booked",
    created_at: new Date(now.getTime() - 48 * 3600 * 1000).toISOString(),
    cancelled_at: null,
    starts_at: MOCK_TEST_DRIVE_SLOTS[2].starts_at,
    ends_at: MOCK_TEST_DRIVE_SLOTS[2].ends_at,
  },
  {
    id: 303,
    slot_id: 205,
    dealership_id: 1,
    vehicle_id: 103,
    vehicle_name: "2024 Audi RS6 Avant",
    customer_id: 503,
    customer_name: "Daniel Rivera",
    customer_email: "daniel.rivera@example.com",
    customer_phone: "+1-212-555-0811",
    status: "completed",
    created_at: new Date(now.getTime() - 72 * 3600 * 1000).toISOString(),
    cancelled_at: null,
    starts_at: new Date(now.getTime() - 12 * 3600 * 1000).toISOString(),
    ends_at: new Date(now.getTime() - 11 * 3600 * 1000).toISOString(),
  },
];

export const MOCK_KNOWLEDGE_DOCUMENTS: KnowledgeDocument[] = [
  {
    id: 401,
    dealership_id: 1,
    brand_id: 1,
    brand_name: "Toyota",
    title: "Toyota 2024 Camry Specs & Warranty Guide.pdf",
    mime_type: "application/pdf",
    source_file: "toyota_camry_2024_manual.pdf",
    chunk_count: 14,
    created_at: "2026-11-18T14:30:00Z",
    status: "ready",
  },
  {
    id: 402,
    dealership_id: 1,
    brand_id: null,
    brand_name: "All Brands",
    title: "Apex Motors Test Drive Customer Agreement & Safety.pdf",
    mime_type: "application/pdf",
    source_file: "test_drive_safety_v2.pdf",
    chunk_count: 8,
    created_at: "2026-11-19T09:15:00Z",
    status: "ready",
  },
  {
    id: 403,
    dealership_id: 1,
    brand_id: 2,
    brand_name: "BMW",
    title: "BMW M-Series Maintenance Schedule & Track Terms.md",
    mime_type: "text/markdown",
    source_file: "bmw_m_track_policy.md",
    chunk_count: 6,
    created_at: "2026-11-20T11:00:00Z",
    status: "ready",
  },
];

export const MOCK_STAFF: StaffUser[] = [
  { id: 1, dealership_id: 1, name: "Marcus Vance", email: "marcus@apexmotors.com", role: "dealership_admin", is_active: true, last_login: "Just now" },
  { id: 2, dealership_id: 1, name: "Sarah Jenkins", email: "sarah.j@apexmotors.com", role: "manager", is_active: true, last_login: "18m ago" },
  { id: 3, dealership_id: 1, name: "Carlos Reyes", email: "carlos.r@apexmotors.com", role: "sales_rep", is_active: true, last_login: "2h ago" },
  { id: 4, dealership_id: 1, name: "Emma Watson", email: "emma.w@apexmotors.com", role: "sales_rep", is_active: true, last_login: "Yesterday" },
];

export const MOCK_INVITATIONS: StaffInvitation[] = [
  { id: 1, dealership_id: 1, name: "Tyler Brooks", email: "tyler.b@apexmotors.com", role: "sales_rep", expires_at: "2026-11-27T12:00:00Z", delivery_status: "delivered", status: "pending" },
];

export const MOCK_AUDIT_LOGS: AuditLogItem[] = [
  {
    id: 801,
    dealership_id: 1,
    actor_id: 1,
    actor_email: "marcus@apexmotors.com",
    action: "VEHICLE_CREATED",
    resource_type: "vehicle",
    resource_id: "101",
    ip_address: "192.168.1.10",
    details: { model: "Camry XSE", stock_number: "STK-2024-001", price: 36800 },
    created_at: "2026-11-20T22:15:00Z",
  },
  {
    id: 802,
    dealership_id: 1,
    actor_id: 501,
    actor_email: "sophia.m@example.com",
    action: "TEST_DRIVE_BOOKED",
    resource_type: "test_drive_booking",
    resource_id: "301",
    ip_address: "74.125.210.4",
    details: { slot_id: 201, vehicle: "2024 Toyota Camry", capacity_left: 1 },
    created_at: "2026-11-20T22:30:00Z",
  },
  {
    id: 803,
    dealership_id: 1,
    actor_id: 2,
    actor_email: "sarah.j@apexmotors.com",
    action: "DOCUMENT_INGESTED",
    resource_type: "knowledge_document",
    resource_id: "401",
    ip_address: "192.168.1.14",
    details: { filename: "toyota_camry_2024_manual.pdf", chunks: 14 },
    created_at: "2026-11-20T23:05:00Z",
  },
  {
    id: 804,
    dealership_id: 1,
    actor_id: 1,
    actor_email: "marcus@apexmotors.com",
    action: "STAFF_INVITED",
    resource_type: "staff_invitation",
    resource_id: "1",
    ip_address: "192.168.1.10",
    details: { invited_email: "tyler.b@apexmotors.com", role: "sales_rep" },
    created_at: "2026-11-20T23:40:00Z",
  },
  {
    id: 805,
    dealership_id: 1,
    actor_id: 502,
    actor_email: "liam.chen@example.com",
    action: "LOGIN_SUCCESS",
    resource_type: "user",
    resource_id: "502",
    ip_address: "172.56.21.89",
    details: { user_agent: "Mozilla/5.0 macOS", auth_type: "bearer" },
    created_at: "2026-11-20T23:55:00Z",
  },
];

export const MOCK_HEALTH: HealthStatus = {
  status: "ok",
  db_latency_ms: 12.4,
  database: "connected (PostgreSQL 16.2 on Supabase)",
  services: {
    storage: "ready (brand-logos & vehicle-images)",
    email: "ready (Resend API)",
    embeddings: "ready (text-embedding-3-small)",
    llm: "ready (OpenAI-compatible auto/fallback)",
  },
};
