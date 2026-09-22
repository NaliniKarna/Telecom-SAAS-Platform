export interface PendingRegistration {
  company_id: string;
  company_name: string;
  slug: string;
  status: string;
  contact_phone: string | null;
  admin_user_id: string | null;
  admin_email: string | null;
  admin_name: string | null;
  admin_email_verified: boolean;
  submitted_at: string;
}
