import {
  Directive,
  effect,
  inject,
  Input,
  TemplateRef,
  ViewContainerRef,
} from '@angular/core';

import { Permission } from '../../core/constants/rbac.constants';
import { AuthService } from '../../core/services/auth.service';

/**
 * Renders content only if the current user holds the given permission(s).
 * Reactive: re-evaluates when auth state changes (login/logout/role change).
 *
 *   <button *appHasPermission="Permission.UserCreate">New user</button>
 *   <div *appHasPermission="[Permission.AuditRead, Permission.StatsRead]">…</div>
 */
@Directive({
  selector: '[appHasPermission]',
  standalone: true,
})
export class HasPermissionDirective {
  private readonly auth = inject(AuthService);
  private readonly templateRef = inject(TemplateRef<unknown>);
  private readonly viewContainer = inject(ViewContainerRef);

  private required: Permission[] = [];
  private rendered = false;

  @Input({ required: true })
  set appHasPermission(value: Permission | Permission[]) {
    this.required = Array.isArray(value) ? value : [value];
  }

  constructor() {
    effect(() => {
      // Touch the signal so the effect re-runs on permission changes.
      this.auth.permissions();
      this.auth.isSuperAdmin();

      const allowed = this.auth.hasAnyPermission(this.required);
      if (allowed && !this.rendered) {
        this.viewContainer.createEmbeddedView(this.templateRef);
        this.rendered = true;
      } else if (!allowed && this.rendered) {
        this.viewContainer.clear();
        this.rendered = false;
      }
    });
  }
}
