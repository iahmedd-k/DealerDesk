export interface Dealership {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  address: string | null;
  timezone: string;
  is_active: boolean;
  subscription_plan?: "starter" | "pro" | "enterprise" | string;
  subscription_status?: "active" | "trialing" | "past_due" | "suspended" | string;
  monthly_price?: number;
  max_brands?: number;
  max_vehicles?: number;
  created_at?: string;
  brands_count?: number;
  vehicles_count?: number;
  staff_count?: number;
}

export interface Brand {
  id: number;
  dealership_id: number;
  name: string;
  logo_url: string | null;
  is_active: boolean;
  is_deleted: boolean;
  vehicles_count?: number;
}

export interface VehicleImage {
  id: number;
  vehicle_id: number;
  public_url: string;
  media_type: string;
  alt_text: string | null;
  position: number;
}

export type VehicleStatus = "available" | "reserved" | "sold" | "in_transit" | "unavailable";

export interface VehicleStatusHistory {
  id: number;
  dealership_id: number;
  vehicle_id: number;
  changed_by_user_id: number | null;
  changed_by_user_email?: string | null;
  previous_status: string;
  new_status: string;
  notes: string | null;
  created_at: string;
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
  status?: VehicleStatus;
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

export interface CustomerLead {
  id: number;
  dealership_id: number;
  customer_id: number | null;
  requested_vehicle_id: number | null;
  assigned_to_user_id: number | null;
  test_drive_booking_id: number | null;
  name: string;
  email: string;
  phone: string | null;
  message: string;
  source: string;
  status:
    | "new"
    | "contacted"
    | "qualified"
    | "test_drive_scheduled"
    | "won"
    | "lost"
    | "follow_up";
  consent_to_contact: boolean;
  consented_at: string | null;
  next_follow_up_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocument {
  id: number;
  dealership_id: number;
  brand_id: number | null;
  uploaded_by_user_id?: number;
  filename?: string;
  media_type?: string;
  page_count?: number | null;
  title?: string;
  mime_type?: string;
  source_file?: string;
  brand_name?: string | null;
  chunk_count: number;
  created_at: string;
  processed_at?: string;
  status: string;
}

export interface StaffUser {
  id: number;
  dealership_id: number;
  name: string;
  email: string;
  role: "dealership_admin" | "manager" | "sales_rep" | "dealerdesk_admin";
  is_active: boolean;
}

export interface StaffInvitation {
  id: number | null;
  user_id?: number;
  dealership_id?: number;
  name?: string;
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
  ip_address: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface HealthStatus {
  status: "healthy" | "unhealthy";
  timestamp: string;
  database: {
    status: string;
    latency_ms: number | null;
  };
  services: {
    storage: string;
    email: string;
    embeddings: string;
    llm: string;
  };
}
