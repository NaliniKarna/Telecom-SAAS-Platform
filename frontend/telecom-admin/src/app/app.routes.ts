import { Routes } from '@angular/router';

import { authGuard, guestGuard, rootEntryGuard } from './core/guards/auth.guard';
import {
  landingRedirectGuard,
  permissionGuard,
  roleGuard,
} from './core/guards/rbac.guard';
import { Permission, RoleName } from './core/constants/rbac.constants';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    canActivate: [rootEntryGuard],
    children: [],
  },
  {
    path: 'landing',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/landing/landing.component').then(
        (m) => m.LandingComponent,
      ),
  },
  {
    path: 'solutions/:slug',
    loadComponent: () =>
      import('./features/solutions/solution-page.component').then(
        (m) => m.SolutionPageComponent,
      ),
  },
  {
    path: 'docs',
    loadComponent: () =>
      import('./features/docs/docs.component').then((m) => m.DocsComponent),
  },
  {
    path: 'auth',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./layout/auth-layout/auth-layout.component').then(
        (m) => m.AuthLayoutComponent,
      ),
    children: [
      {
        path: 'login',
        loadComponent: () =>
          import('./features/auth/login.component').then(
            (m) => m.LoginComponent,
          ),
      },
      {
        path: 'register',
        loadComponent: () =>
          import('./features/auth/register-company.component').then(
            (m) => m.RegisterCompanyComponent,
          ),
      },
      {
        path: 'forgot-password',
        loadComponent: () =>
          import('./features/auth/forgot-password.component').then(
            (m) => m.ForgotPasswordComponent,
          ),
      },
      {
        path: 'reset-password',
        loadComponent: () =>
          import('./features/auth/reset-password.component').then(
            (m) => m.ResetPasswordComponent,
          ),
      },
      {
        path: 'verify-email',
        loadComponent: () =>
          import('./features/auth/verify-email.component').then(
            (m) => m.VerifyEmailComponent,
          ),
      },
      {
        path: 'accept-invite',
        loadComponent: () =>
          import('./features/auth/accept-invite.component').then(
            (m) => m.AcceptInviteComponent,
          ),
      },
      { path: '', pathMatch: 'full', redirectTo: 'login' },
    ],
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./layout/main-layout/main-layout.component').then(
        (m) => m.MainLayoutComponent,
      ),
    children: [
      {
        path: 'dashboard',
        canActivate: [permissionGuard([Permission.UserRead])],
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then(
            (m) => m.DashboardComponent,
          ),
      },
      {
        path: 'admin',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/admin/admin-home.component').then(
            (m) => m.AdminHomeComponent,
          ),
      },
      {
        path: 'subscription-plans',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/plans/plan-list.component').then(
            (m) => m.PlanListComponent,
          ),
      },
      {
        path: 'subscription-plans/new',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/plans/plan-form.component').then(
            (m) => m.PlanFormComponent,
          ),
      },
      {
        path: 'subscription-plans/:id/edit',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/plans/plan-form.component').then(
            (m) => m.PlanFormComponent,
          ),
      },
      {
        path: 'subscription-plans/:id',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/plans/plan-detail.component').then(
            (m) => m.PlanDetailComponent,
          ),
      },
      {
        path: 'settings',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/settings/settings.component').then(
            (m) => m.PlatformSettingsComponent,
          ),
      },
      {
        path: 'registration/pending',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/registration/pending-registrations.component').then((m) => m.PendingRegistrationsComponent),
      },
      {
        path: 'admin/ai-voice',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'voices' },
          {
            path: 'voices',
            loadComponent: () =>
              import('./features/admin-ai-voice/admin-voice-list.component').then((m) => m.AdminVoiceListComponent),
          },
          {
            path: 'preview',
            loadComponent: () =>
              import('./features/admin-ai-voice/admin-tts-preview.component').then((m) => m.AdminTtsPreviewComponent),
          },
        ],
      },
      {
        path: 'telephony',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/telephony/telephony.component').then(
            (m) => m.TelephonyComponent,
          ),
      },
      {
        path: 'users',
        canActivate: [permissionGuard([Permission.UserRead])],
        loadComponent: () =>
          import('./features/users/user-list.component').then(
            (m) => m.UserListComponent,
          ),
      },
      {
        path: 'users/:id',
        canActivate: [permissionGuard([Permission.UserRead])],
        loadComponent: () =>
          import('./features/users/user-detail.component').then(
            (m) => m.UserDetailComponent,
          ),
      },
      {
        path: 'groups',
        canActivate: [permissionGuard([Permission.GroupManage])],
        loadComponent: () =>
          import('./features/groups/group-list.component').then(
            (m) => m.GroupListComponent,
          ),
      },
      {
        path: 'groups/:id',
        canActivate: [permissionGuard([Permission.GroupManage])],
        loadComponent: () =>
          import('./features/groups/group-detail.component').then(
            (m) => m.GroupDetailComponent,
          ),
      },
      {
        path: 'api-keys',
        canActivate: [permissionGuard([Permission.ApiKeyRead])],
        loadComponent: () =>
          import('./features/api-keys/api-key-list.component').then(
            (m) => m.ApiKeyListComponent,
          ),
      },
      {
        path: 'contacts',
        canActivate: [permissionGuard([Permission.ContactRead])],
        loadComponent: () =>
          import('./features/contacts/contact-list.component').then(
            (m) => m.ContactListComponent,
          ),
      },
      {
        path: 'contact-lists',
        canActivate: [permissionGuard([Permission.ContactRead])],
        loadComponent: () =>
          import('./features/contacts/contact-group-list.component').then(
            (m) => m.ContactGroupListComponent,
          ),
      },
      {
        path: 'contact-lists/:id',
        canActivate: [permissionGuard([Permission.ContactRead])],
        loadComponent: () =>
          import('./features/contacts/contact-group-detail.component').then(
            (m) => m.ContactGroupDetailComponent,
          ),
      },
      {
        path: 'company-settings',
        canActivate: [permissionGuard([Permission.CompanyRead])],
        loadComponent: () =>
          import(
            './features/company-settings/company-settings.component'
          ).then((m) => m.CompanySettingsComponent),
      },
      {
        path: 'sms',
        canActivate: [permissionGuard([Permission.SmsRead])],
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'sender-ids' },
          {
            path: 'sender-ids',
            loadComponent: () =>
              import('./features/sms/sms-sender-ids.component').then((m) => m.SmsSenderIdsComponent),
          },
          {
            path: 'templates',
            loadComponent: () =>
              import('./features/sms/sms-template-list.component').then((m) => m.SmsTemplateListComponent),
          },
          {
            path: 'campaigns',
            loadComponent: () =>
              import('./features/sms/sms-campaign-list.component').then((m) => m.SmsCampaignListComponent),
          },
          {
            path: 'campaigns/new',
            canActivate: [permissionGuard([Permission.SmsManage])],
            loadComponent: () =>
              import('./features/sms/sms-campaign-form.component').then((m) => m.SmsCampaignFormComponent),
          },
          {
            path: 'campaigns/:id/edit',
            canActivate: [permissionGuard([Permission.SmsManage])],
            loadComponent: () =>
              import('./features/sms/sms-campaign-form.component').then((m) => m.SmsCampaignFormComponent),
          },
          {
            path: 'campaigns/:id',
            loadComponent: () =>
              import('./features/sms/sms-campaign-detail.component').then((m) => m.SmsCampaignDetailComponent),
          },
          {
            path: 'analytics',
            canActivate: [permissionGuard([Permission.SmsAnalytics])],
            loadComponent: () =>
              import('./features/sms/sms-analytics.component').then((m) => m.SmsAnalyticsComponent),
          },
          {
            path: 'messages',
            loadComponent: () =>
              import('./features/sms/sms-messages.component').then((m) => m.SmsMessagesComponent),
          },
        ],
      },
      // ---- Voice module ----
      {
        path: 'voice',
        canActivate: [permissionGuard([Permission.VoiceRead])],
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
          {
            path: 'dashboard',
            loadComponent: () =>
              import('./features/voice/voice-dashboard.component').then(
                (m) => m.VoiceDashboardComponent,
              ),
          },
          {
            path: 'extensions',
            loadComponent: () =>
              import('./features/voice/voice-extensions.component').then(
                (m) => m.VoiceExtensionsComponent,
              ),
          },
          {
            path: 'dialer',
            canActivate: [permissionGuard([Permission.VoiceDial])],
            loadComponent: () =>
              import('./features/voice/voice-dialer.component').then(
                (m) => m.VoiceDialerComponent,
              ),
          },
          {
            path: 'active',
            loadComponent: () =>
              import('./features/voice/voice-active-calls.component').then(
                (m) => m.VoiceActiveCallsComponent,
              ),
          },
          {
            path: 'calls',
            loadComponent: () =>
              import('./features/voice/voice-call-history.component').then(
                (m) => m.VoiceCallHistoryComponent,
              ),
          },
          {
            path: 'analytics',
            loadComponent: () =>
              import('./features/voice/voice-analytics.component').then(
                (m) => m.VoiceAnalyticsComponent,
              ),
          },
        ],
      },
      // ---- Missed Call module ----
      {
        path: 'missed-calls',
        canActivate: [permissionGuard([Permission.MissedCallRead])],
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
          {
            path: 'dashboard',
            loadComponent: () =>
              import('./features/missed-calls/missed-call-dashboard.component').then(
                (m) => m.MissedCallDashboardComponent,
              ),
          },
          {
            path: 'list',
            loadComponent: () =>
              import('./features/missed-calls/missed-call-list.component').then(
                (m) => m.MissedCallListComponent,
              ),
          },
          {
            path: ':id',
            loadComponent: () =>
              import('./features/missed-calls/missed-call-detail.component').then(
                (m) => m.MissedCallDetailComponent,
              ),
          },
        ],
      },
      {
        path: 'ai-voice',
        canActivate: [permissionGuard([Permission.AiVoiceRead])],
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'templates' },
          {
            path: 'voices',
            loadComponent: () =>
              import('./features/ai-voice/voice-list.component').then((m) => m.VoiceListComponent),
          },
          {
            path: 'templates',
            loadComponent: () =>
              import('./features/ai-voice/voice-template-list.component').then((m) => m.VoiceTemplateListComponent),
          },
          {
            path: 'templates/:id/preview',
            canActivate: [permissionGuard([Permission.AiVoicePreview])],
            loadComponent: () =>
              import('./features/ai-voice/voice-template-preview.component').then((m) => m.VoiceTemplatePreviewComponent),
          },
        ],
      },
      {
        path: 'voice-campaigns',
        canActivate: [permissionGuard([Permission.AiVoiceCampaignRead])],
        children: [
          {
            path: '',
            pathMatch: 'full',
            loadComponent: () =>
              import('./features/voice-campaigns/voice-campaign-list.component').then((m) => m.VoiceCampaignListComponent),
          },
          {
            path: 'new',
            canActivate: [permissionGuard([Permission.AiVoiceCampaignManage])],
            loadComponent: () =>
              import('./features/voice-campaigns/voice-campaign-form.component').then((m) => m.VoiceCampaignFormComponent),
          },
          {
            path: ':id/edit',
            canActivate: [permissionGuard([Permission.AiVoiceCampaignManage])],
            loadComponent: () =>
              import('./features/voice-campaigns/voice-campaign-form.component').then((m) => m.VoiceCampaignFormComponent),
          },
          {
            path: ':id',
            loadComponent: () =>
              import('./features/voice-campaigns/voice-campaign-detail.component').then((m) => m.VoiceCampaignDetailComponent),
          },
        ],
      },
      {
        path: 'sms-approvals',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/sms/sms-sender-approvals.component').then((m) => m.SmsSenderApprovalsComponent),
      },
      {
        path: 'profile',
        loadComponent: () =>
          import('./features/profile/profile.component').then(
            (m) => m.ProfileComponent,
          ),
      },
      {
        path: 'change-requests',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/change-requests/change-requests.component').then(
            (m) => m.ChangeRequestsComponent,
          ),
      },
      {
        path: 'companies',
        canActivate: [permissionGuard([Permission.CompanyRead])],
        children: [
          {
            path: '',
            loadComponent: () =>
              import('./features/companies/company-list.component').then(
                (m) => m.CompanyListComponent,
              ),
          },
          {
            path: 'new',
            canActivate: [permissionGuard([Permission.CompanyCreate])],
            loadComponent: () =>
              import('./features/companies/company-form.component').then(
                (m) => m.CompanyFormComponent,
              ),
          },
          {
            path: ':id/edit',
            canActivate: [permissionGuard([Permission.CompanyUpdate])],
            loadComponent: () =>
              import('./features/companies/company-form.component').then(
                (m) => m.CompanyFormComponent,
              ),
          },
          {
            path: ':id',
            loadComponent: () =>
              import('./features/companies/company-detail.component').then(
                (m) => m.CompanyDetailComponent,
              ),
          },
        ],
      },
      {
        path: 'audit-logs',
        canActivate: [permissionGuard([Permission.AuditRead])],
        loadComponent: () =>
          import('./features/audit/audit-log-list.component').then(
            (m) => m.AuditLogListComponent,
          ),
      },
      { path: '', pathMatch: 'full', canActivate: [landingRedirectGuard], children: [] },
    ],
  },
  {
    path: 'forbidden',
    loadComponent: () =>
      import('./features/errors/forbidden.component').then(
        (m) => m.ForbiddenComponent,
      ),
  },
  { path: '**', redirectTo: '' },
];