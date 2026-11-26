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
  budget?: number | null;
  purchase_timeline?: string | null;
  conversation_id?: number | null;
  preferences?: Record<string, unknown> | null;
  deal_value?: number | null;
  deal_notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadActivity {
  id: number;
  dealership_id: number;
  lead_id: number;
  actor_user_id: number | null;
  actor_user_email?: string | null;
  activity_type: string;
  summary: string;
  details?: Record<string, unknown> | null;
  created_at: string;
}

export interface ConversationMessageItem {
  id: number;
  conversation_id: number;
  sender_type: "customer" | "agent" | "staff" | "system" | string;
  sender_id: number | null;
  content: string;
  channel_metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface ConversationSummary {
  id: number;
  dealership_id: number;
  channel: "website" | "whatsapp" | "voice" | string;
  channel_user_id: string;
  customer_id: number | null;
  status: "active" | "handed_off" | "closed" | string;
  assigned_to_user_id: number | null;
  assigned_to_name: string | null;
  handoff_reason: string | null;
  last_message_preview: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ConversationMessageItem[];
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
  is_available?: boolean;
  availability_note?: string | null;
}

export interface TestDriveSettings {
  id?: number;
  dealership_id?: number;
  opening_time: string;
  closing_time: string;
  slot_duration_minutes: number;
  capacity_per_slot: number;
  days_open: number[];
  timezone?: string;
}

export interface OperationsSummary {
  dealership_id: number;
  inventory: { total: number; by_status: Record<string, number>; total_value: number };
  leads: { total: number; by_status: Record<string, number>; won_deal_value: number };
  test_drives: { total: number; by_status: Record<string, number> };
  conversations: { total: number; by_channel: Record<string, number>; handoff_queue: number };
  observability: { outbox_by_status: Record<string, number>; notifications_by_status: Record<string, number> };
}

export interface NotificationDelivery {
  id: number;
  booking_id: number | null;
  notification_type: string;
  channel: string;
  recipient: string;
  status: string;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface OutboxEvent {
  id: number;
  event_type: string;
  aggregate_type: string;
  aggregate_id: string;
  status: string;
  attempts: number;
  last_error: string | null;
  next_retry_at: string | null;
  delivered_at: string | null;
  created_at: string;
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
