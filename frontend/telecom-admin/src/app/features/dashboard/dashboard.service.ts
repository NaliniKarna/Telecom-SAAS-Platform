import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { CompanyDashboardOverview, DashboardOverview } from './dashboard.models';

@Injectable({ providedIn: 'root' })
export class DashboardApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/dashboard`;

  overview(): Observable<DashboardOverview> {
    return this.http.get<DashboardOverview>(`${this.baseUrl}/overview`);
  }

  companyOverview(): Observable<CompanyDashboardOverview> {
    return this.http.get<CompanyDashboardOverview>(
      `${this.baseUrl}/company-overview`,
    );
  }
}
