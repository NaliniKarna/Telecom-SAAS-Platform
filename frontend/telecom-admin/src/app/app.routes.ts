import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/guards/auth.guard';
import {
  landingRedirectGuard,
  permissionGuard,
  roleGuard,
} from './core/guards/rbac.guard';
import { Permission, RoleName } from './core/constants/rbac.constants';

/**
 * Top-level routing. Two shells: AuthLayout for public pages, MainLayout for
 * the authenticated app. Feature areas are lazy-loaded; the routes below are
 * the foundation. Feature module routes plug in under MainLayout's children.
 */
export const routes: Routes = [
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
      {
        // Super-admin sender ID approval queue (cross-company). Company admins
        // create sender IDs but cannot approve their own.
        path: 'sms-approvals',
        canActivate: [roleGuard([RoleName.SuperAdmin])],
        loadComponent: () =>
          import('./features/sms/sms-sender-approvals.component').then((m) => m.SmsSenderApprovalsComponent),
      },
      {
        // Available to every authenticated user (super admin, company admin,
        // company user). No permission guard — just an authenticated session.
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
      // Feature module routes (companies, users, api-keys, audit-logs) mount
      // here, each guarded with permissionGuard([...]) per the RBAC contract.
      {
        path: 'audit-logs',
        canActivate: [permissionGuard([Permission.AuditRead])],
        loadComponent: () =>
          import('./features/audit/audit-log-list.component').then(
            (m) => m.AuditLogListComponent,
          ),
      },
      // Root index: send the user to their role-based landing route.
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
  { path: '**', redirectTo: 'dashboard' },
];
