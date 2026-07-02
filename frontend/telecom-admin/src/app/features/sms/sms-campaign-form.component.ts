import { Component, inject, signal } from '@angular/core';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { SmsService } from './sms.service';
import { SmsSenderId, SmsTemplate, CampaignSource } from './sms.models';
import { ContactService } from '../contacts/contact.service';
import { ContactListService } from '../contacts/contact-list.service';
import { ContactListItem, ContactGroup } from '../contacts/contact.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-sms-campaign-form',
  standalone: true,
  imports: [
    RouterLink, ReactiveFormsModule, MatCardModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatProgressBarModule,
  ],
  template: `
    <a mat-button routerLink="/sms/campaigns"><mat-icon>arrow_back</mat-icon> Campaigns</a>
    <header class="page-header"><h1>{{ editing ? 'Edit campaign' : 'New campaign' }}</h1></header>
    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    <mat-card appearance="outlined" class="form-card">
      <form [formGroup]="form" class="form">
        <mat-form-field appearance="outline">
          <mat-label>Campaign name</mat-label>
          <input matInput formControlName="name" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Sender ID</mat-label>
          <mat-select formControlName="sender_id">
            @for (s of senders(); track s.id) {
              <mat-option [value]="s.id">{{ s.sender_id }} — {{ s.name }}</mat-option>
            }
          </mat-select>
          <mat-hint>Only approved &amp; active sender IDs can send.</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Template</mat-label>
          <mat-select formControlName="template_id">
            @for (t of templates(); track t.id) {
              <mat-option [value]="t.id">{{ t.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Recipient source</mat-label>
          <mat-select formControlName="source_type">
            <mat-option value="contact_list">Contact list</mat-option>
            <mat-option value="contacts">Individual contacts</mat-option>
          </mat-select>
        </mat-form-field>

        @if (form.controls.source_type.value === 'contact_list') {
          <mat-form-field appearance="outline">
            <mat-label>Contact list</mat-label>
            <mat-select formControlName="source_list_id">
              @for (l of lists(); track l.id) {
                <mat-option [value]="l.id">{{ l.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
        }
        @if (form.controls.source_type.value === 'contacts') {
          <mat-form-field appearance="outline">
            <mat-label>Contacts</mat-label>
            <mat-select formControlName="contact_ids" multiple>
              @for (c of contacts(); track c.id) {
                <mat-option [value]="c.id">{{ c.first_name }} {{ c.last_name }} ({{ c.mobile_e164 || 'no mobile' }})</mat-option>
              }
            </mat-select>
            <mat-hint>Contacts without a mobile number are skipped at send.</mat-hint>
          </mat-form-field>
        }

        <div class="actions">
          <button mat-button type="button" routerLink="/sms/campaigns">Cancel</button>
          <button mat-flat-button color="primary" type="button" (click)="submit()" [disabled]="saving() || form.invalid">
            {{ editing ? 'Save draft' : 'Create draft' }}
          </button>
        </div>
      </form>
    </mat-card>
  `,
  styles: [`
    .page-header h1 { margin: .5rem 0 1rem; }
    .form-card { max-width: 640px; }
    .form { display: flex; flex-direction: column; gap: .5rem; padding-top: .5rem; }
    .actions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: 1rem; }
  `],
})
export class SmsCampaignFormComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(SmsService);
  private readonly contactsApi = inject(ContactService);
  private readonly listsApi = inject(ContactListService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly notify = inject(NotificationService);

  readonly saving = signal(false);
  readonly loading = signal(false);
  readonly senders = signal<SmsSenderId[]>([]);
  readonly templates = signal<SmsTemplate[]>([]);
  readonly lists = signal<ContactGroup[]>([]);
  readonly contacts = signal<ContactListItem[]>([]);
  readonly editing: boolean;
  private id: string | null;

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    sender_id: ['', [Validators.required]],
    template_id: ['', [Validators.required]],
    source_type: this.fb.nonNullable.control<CampaignSource>('contact_list'),
    source_list_id: this.fb.control<string | null>(null),
    contact_ids: this.fb.nonNullable.control<string[]>([]),
  });

  constructor() {
    this.id = this.route.snapshot.paramMap.get('id');
    this.editing = !!this.id;
    // Approved + active senders only.
    this.api.listSenderIds({ approval_status: 'approved', status: 'active', size: 100 })
      .subscribe((r) => this.senders.set(r.data));
    this.api.listTemplates({ status: 'active', size: 100 }).subscribe((r) => this.templates.set(r.data));
    this.listsApi.list('', 1, 100).subscribe((r) => this.lists.set(r.data));
    this.contactsApi.list({ size: 100 }).subscribe((r) => this.contacts.set(r.data));
    if (this.editing && this.id) this.loadCampaign(this.id);
  }

  loadCampaign(id: string): void {
    this.loading.set(true);
    this.api.getCampaign(id).subscribe({
      next: (c) => {
        this.form.patchValue({
          name: c.name,
          sender_id: c.sender_id ?? '',
          template_id: c.template_id ?? '',
          source_type: c.source_type,
          source_list_id: (c as { source_list_id?: string | null }).source_list_id ?? null,
        });
        this.loading.set(false);
      },
      error: () => { this.loading.set(false); this.notify.error('Unable to load campaign.'); },
    });
  }

  submit(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    const v = this.form.getRawValue();
    if (v.source_type === 'contact_list' && !v.source_list_id) { this.notify.error('Choose a contact list.'); return; }
    if (v.source_type === 'contacts' && v.contact_ids.length === 0) { this.notify.error('Choose at least one contact.'); return; }
    this.saving.set(true);
    const payload = {
      name: v.name, sender_id: v.sender_id, template_id: v.template_id,
      source_type: v.source_type,
      source_list_id: v.source_type === 'contact_list' ? v.source_list_id : null,
      contact_ids: v.source_type === 'contacts' ? v.contact_ids : [],
    };
    const done = {
      next: (c: { id: string }) => { this.notify.success('Campaign saved.'); this.router.navigate(['/sms/campaigns', c.id]); },
      error: () => this.saving.set(false),
    };
    if (this.editing && this.id) this.api.updateCampaign(this.id, payload).subscribe(done);
    else this.api.createCampaign(payload).subscribe(done);
  }
}
