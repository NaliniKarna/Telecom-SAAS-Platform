export type SenderStatus = 'active' | 'inactive';
export type SenderApprovalStatus = 'pending' | 'approved' | 'rejected';
export type TemplateStatus = 'active' | 'inactive';

export interface SmsSenderId {
  id: string;
  name: string;
  sender_id: string;
  description: string | null;
  status: SenderStatus;
  approval_status: SenderApprovalStatus;
  is_default: boolean;
  rejection_reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SmsSenderReviewItem {
  id: string;
  company_id: string;
  company_name: string | null;
  name: string;
  sender_id: string;
  description: string | null;
  approval_status: SenderApprovalStatus;
  created_at: string;
}

export interface SmsTemplate {
  id: string;
  name: string;
  body: string;
  variables: string[];
  status: TemplateStatus;
  created_at: string;
  updated_at: string;
}

export interface SenderIdCreate {
  name: string;
  sender_id: string;
  description?: string | null;
}
export interface SenderIdUpdate {
  name?: string;
  description?: string | null;
}
export interface TemplateCreate {
  name: string;
  body: string;
  status?: TemplateStatus;
}
export interface TemplateUpdate {
  name?: string;
  body?: string;
  status?: TemplateStatus;
}
export interface TemplatePreview {
  variables: string[];
  body: string;
}

export interface Paginated<T> {
  data: T[];
  meta: { page: number; size: number; total: number; pages: number };
}

// ----- Campaign Engine -----
export type CampaignStatus =
  | 'draft' | 'scheduled' | 'processing' | 'completed' | 'cancelled' | 'failed';
export type CampaignSource = 'contact_list' | 'contacts';
export type MessageStatus = 'queued' | 'sent' | 'delivered' | 'failed';

export interface SmsCampaign {
  id: string;
  name: string;
  sender_id: string | null;
  template_id: string | null;
  status: CampaignStatus;
  source_type: CampaignSource;
  schedule_time: string | null;
  total_recipients: number;
  sent_count: number;
  delivered_count: number;
  failed_count: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface SmsCampaignListItem {
  id: string;
  name: string;
  status: CampaignStatus;
  source_type: CampaignSource;
  schedule_time: string | null;
  total_recipients: number;
  sent_count: number;
  delivered_count: number;
  failed_count: number;
  created_at: string;
}

export interface CampaignCreate {
  name: string;
  sender_id: string;
  template_id: string;
  source_type: CampaignSource;
  source_list_id?: string | null;
  contact_ids?: string[];
}
export interface CampaignUpdate {
  name?: string;
  sender_id?: string;
  template_id?: string;
  source_type?: CampaignSource;
  source_list_id?: string | null;
  contact_ids?: string[];
}

export interface CampaignRecipient {
  id: string;
  contact_id: string | null;
  phone_e164: string;
  resolved_name: string | null;
  created_at: string;
}

export interface CampaignMessage {
  id: string;
  campaign_id: string | null;
  recipient_phone: string;
  sender_id: string | null;
  content: string;
  status: MessageStatus;
  error_details: string | null;
  provider_message_id: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  created_at: string;
}

// ----- Tracking & Analytics -----
export interface AnalyticsOverview {
  total_messages: number;
  delivered_messages: number;
  failed_messages: number;
  sent_messages: number;
  queued_messages: number;
  delivery_rate: number;
  campaign_count: number;
  active_campaigns: number;
}

export interface AnalyticsTimePoint {
  date: string;
  total: number;
  delivered: number;
  failed: number;
}

export interface AnalyticsFilters {
  campaign_id?: string | null;
  sender_id?: string | null;
  since?: string | null;
  until?: string | null;
}
