export interface DashboardKpis {
  total_companies: number;
  active_companies: number;
  suspended_companies: number;
  deactivated_companies: number;
  total_plans: number;
}

export interface RecentCompany {
  id: string;
  name: string;
  status: string;
  plan_name: string | null;
  created_at: string;
}

export interface RecentActivity {
  id: number;
  action: string;
  entity_type: string;
  actor_name: string | null;
  company_name: string | null;
  created_at: string;
}

export interface PlanDistribution {
  plan_id: string | null;
  plan_name: string;
  company_count: number;
}

export interface DashboardOverview {
  kpis: DashboardKpis;
  recent_companies: RecentCompany[];
  recent_activity: RecentActivity[];
  plan_distribution: PlanDistribution[];
}

// --- Company workspace dashboard ---
export interface CompanyKpis {
  total_users: number;
  active_users: number;
  total_groups: number;
  total_api_keys: number;
  total_contacts: number;
  total_contact_lists: number;
  total_sms_campaigns: number;
  total_sms_templates: number;
  total_sms_sender_ids: number;
  total_sms_messages: number;
  messages_sent_today: number;
  delivery_rate: number;
}

export interface CompanySummary {
  company_name: string;
  plan_name: string | null;
  plan_status: string;
  user_limit: number | null;
  current_user_count: number;
}

export interface RecentCompanyUser {
  id: string;
  email: string;
  full_name: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CompanyDashboardOverview {
  kpis: CompanyKpis;
  summary: CompanySummary;
  recent_created_users: RecentCompanyUser[];
  recent_updated_users: RecentCompanyUser[];
}
