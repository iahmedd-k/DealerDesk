export interface Dealership {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  whatsapp_number?: string | null;
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
  acquisition_cost?: number | null;
  location?: string | null;
  reconditioning_status?: "not_required" | "needed" | "in_progress" | "complete";
  acquired_at?: string | null;
  days_in_stock?: number;
  stock_number: string;
  vin?: string | null;
  mileage?: number | null;
  transmission?: string | null;
  fuel_type?: string | null;
  drivetrain?: string | null;
  exterior_color?: string | null;
  interior_color?: string | null;
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
  status: "booked" | "completed" | "no_show" | "cancelled";
  assigned_to_user_id?: number | null;
  outcome_at?: string | null;
  outcome_notes?: string | null;
  created_at: string;
  cancelled_at: string | null;
  starts_at?: string;
  ends_at?: string;
}

export interface ServiceAppointment {
  id: number;
  dealership_id: number;
  vehicle_id: number | null;
  customer_name: string;
  customer_email: string | null;
  customer_phone: string | null;
  scheduled_at: string;
  concern: string;
  status: "scheduled" | "confirmed" | "completed" | "cancelled" | "no_show";
  assigned_to_user_id: number | null;
  notes: string | null;
  completed_at: string | null;
  created_by_user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ServiceWorkOrder {
  id: number;
  dealership_id: number;
  appointment_id: number | null;
  vehicle_id: number | null;
  customer_name: string;
  customer_email: string | null;
  customer_phone: string | null;
  concern: string;
  diagnosis: string | null;
  status: "open" | "in_progress" | "completed" | "cancelled";
  labor_cost: number;
  parts_cost: number;
  total_cost: number;
  follow_up_at: string | null;
  follow_up_status: "not_required" | "pending" | "completed";
  follow_up_notes: string | null;
  created_by_user_id: number | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface VehicleWarranty {
  id: number;
  dealership_id: number;
  vehicle_id: number;
  provider: string;
  policy_number: string | null;
  coverage: string;
  start_date: string;
  end_date: string;
  mileage_limit: number | null;
  notes: string | null;
  created_by_user_id: number | null;
  created_at: string;
  is_active: boolean;
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
  lost_reason?:
    | "price"
    | "vehicle_unavailable"
    | "bought_elsewhere"
    | "financing"
    | "timing"
    | "no_response"
    | "other"
    | null;
  consent_to_contact: boolean;
  consented_at: string | null;
  email_consent: boolean;
  email_consented_at: string | null;
  email_opted_out_at: string | null;
  sms_consent: boolean;
  sms_consented_at: string | null;
  sms_opted_out_at: string | null;
  whatsapp_consent: boolean;
  whatsapp_consented_at: string | null;
  whatsapp_opted_out_at: string | null;
  next_follow_up_at: string | null;
  budget?: number | null;
  purchase_timeline?: string | null;
  conversation_id?: number | null;
  preferences?: Record<string, unknown> | null;
  deal_value?: number | null;
  deal_notes?: string | null;
  trade_in_vehicle?: string | null;
  trade_in_value?: number | null;
  down_payment?: number | null;
  apr_percent?: number | null;
  loan_term_months?: number | null;
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

export interface LeadQuote {
  id: number;
  dealership_id: number;
  lead_id: number;
  version: number;
  status: "draft" | "sent" | "accepted" | "declined" | "expired";
  vehicle_id: number | null;
  vehicle_label: string | null;
  sale_price: number;
  trade_in_vehicle: string | null;
  trade_in_value: number;
  down_payment: number;
  amount_financed: number;
  apr_percent: number;
  loan_term_months: number;
  estimated_monthly_payment: number;
  disclaimer: string;
  notes: string | null;
  created_by_user_id: number | null;
  created_at: string;
  updated_at: string;
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
  channel: "website" | "whatsapp" | "voice" | "email" | string;
  channel_user_id: string;
  email_subject?: string | null;
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

export interface GmailMailboxStatus {
  connected: boolean;
  email: string | null;
  last_synced_at: string | null;
  next_sync_at?: string | null;
  last_sync_error?: string | null;
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
  leads: {
    total: number;
    by_status: Record<string, number>;
    deal_value_by_status: Record<string, number>;
    by_source: Record<string, number>;
    won_deal_value: number;
  };
  test_drives: { total: number; by_status: Record<string, number> };
  conversations: { total: number; by_channel: Record<string, number>; handoff_queue: number };
  observability: { outbox_by_status: Record<string, number>; notifications_by_status: Record<string, number> };
}

export interface DealershipAnalytics {
  start_date: string;
  end_date: string;
  leads: {
    total: number;
    won: number;
    conversion_rate: number;
    by_status: Record<string, number>;
  };
  by_source: Array<{
    source: string;
    leads: number;
    won: number;
    conversion_rate: number;
    won_deal_value: number;
  }>;
  by_rep: Array<{
    user_id: number | null;
    name: string;
    leads: number;
    won: number;
    conversion_rate: number;
    won_deal_value: number;
  }>;
  historical: {
    daily: Array<{
      date: string;
      leads_created: number;
      won: number;
      lost: number;
    }>;
    stage_transitions: Record<string, number>;
    lost_by_reason: Record<string, number>;
    wins_by_rep_at_close: Array<{
      user_id: number | null;
      name: string;
      won: number;
      won_deal_value: number;
    }>;
  };
  test_drives: { total: number };
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

export interface InAppNotification {
  id: string;
  title: string;
  message: string;
  href: string;
  severity: "urgent" | "high" | "normal" | string;
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
