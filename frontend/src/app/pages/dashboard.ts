import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { RouterLink } from '@angular/router';

import { Api, Claim, Match, Notification, UserDashboard, errorMessage } from '../core/api';
import { Auth } from '../core/auth';
import { Alerts } from '../core/alerts';
import { Breadcrumbs } from '../shared/breadcrumbs';
import { ItemCard } from '../shared/item-card';

const CLAIM_LABELS: Record<string, string> = {
  PENDING: 'Waiting for staff review',
  APPROVED: 'Approved',
  REJECTED: 'Not approved',
  WITHDRAWN: 'Withdrawn',
  COMPLETED: 'Returned to you',
};

interface ShownQr {
  claimId: number;
  image: SafeUrl;
  expiresAt: string;
}

@Component({
  selector: 'app-dashboard',
  imports: [FormsModule, RouterLink, DatePipe, DecimalPipe, Breadcrumbs, ItemCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page stack">
      <app-breadcrumbs [crumbs]="[{ label: 'Home', link: '/' }, { label: 'My dashboard' }]" />
      <h1>My dashboard</h1>
      <p class="muted" style="margin-top: -8px">Signed in as {{ auth.user()?.name }} ({{ auth.user()?.email }})</p>
      @if (error()) { <div class="alert alert-error" role="alert">{{ error() }}</div> }

      @if (data(); as d) {
        <div class="stat-grid">
          <div class="stat lost"><span>Open lost reports</span><strong>{{ d.reports.LOST['OPEN'] + d.reports.LOST['MATCHED'] }}</strong></div>
          <div class="stat found"><span>Open found reports</span><strong>{{ d.reports.FOUND['OPEN'] + d.reports.FOUND['MATCHED'] }}</strong></div>
          <div class="stat"><span>Claims in progress</span><strong>{{ d.claims['PENDING'] + d.claims['APPROVED'] }}</strong></div>
          <div class="stat"><span>Unread notifications</span><strong>{{ d.unread_notifications }}</strong></div>
        </div>

        <div class="grid-2">
          <section class="panel" aria-labelledby="claims-heading">
            <h2 id="claims-heading">My claims</h2>
            @if (!claims().length) { <p class="muted">You have not claimed any items.</p> }
            <ul class="list">
              @for (c of claims(); track c.id) {
                <li>
                  <div class="spread">
                    <a [routerLink]="['/items', c.item.id]"><strong>{{ c.item.title }}</strong></a>
                    <span class="tag tag-status">{{ claimLabels[c.status] }}</span>
                  </div>
                  <p class="small muted" style="margin: 4px 0">Submitted {{ c.created_at | date: 'mediumDate' }}</p>
                  @if (c.review_reason) { <p class="small" style="margin: 4px 0">Staff note: {{ c.review_reason }}</p> }
                  @if (c.status === 'APPROVED') {
                    @if (c.handover?.status === 'SCHEDULED') {
                      @if (qr()?.claimId === c.id) {
                        <div class="qr stack" style="margin-top: 8px">
                          <img [src]="qr()!.image" alt="Handover QR code for {{ c.item.title }}" width="240" height="240" />
                          <p class="small">Show this code and your campus ID at the lost and found desk. It expires at {{ qr()!.expiresAt | date: 'shortTime' }} and works once.</p>
                        </div>
                      }
                      <button class="btn btn-sm" type="button" (click)="showQr(c)">{{ qr()?.claimId === c.id ? 'Get a new code' : 'Show handover QR code' }}</button>
                    } @else if (c.handover?.status === 'VERIFIED') {
                      <p class="small">Code scanned. Staff are completing the handover.</p>
                    } @else {
                      <p class="small">Staff will let you know when the item is ready to collect.</p>
                    }
                  }
                  @if (c.status === 'PENDING' || c.status === 'APPROVED') {
                    <button class="link-btn small" type="button" style="margin-top: 6px" (click)="withdraw(c)">Withdraw claim</button>
                  }
                </li>
              }
            </ul>
          </section>

          <section class="panel" aria-labelledby="matches-heading">
            <h2 id="matches-heading">Possible matches for my reports</h2>
            @if (!d.top_suggestions.length) { <p class="muted">No open suggestions right now.</p> }
            <ul class="list">
              @for (m of d.top_suggestions; track m.id) {
                <li class="spread">
                  <span>
                    <a [routerLink]="['/items', m.counterpart.id]">{{ m.counterpart.title }}</a>
                    <span class="small muted"> at {{ m.counterpart.location.name }}</span>
                  </span>
                  <a class="btn btn-outline btn-sm" [routerLink]="['/items', myItemId(m)]">Review ({{ m.score | number: '1.0-0' }}%)</a>
                </li>
              }
            </ul>
          </section>
        </div>

        <section aria-labelledby="reports-heading">
          <div class="spread" style="margin-bottom: 12px">
            <h2 id="reports-heading" style="margin: 0">My recent reports</h2>
            <a routerLink="/items" [queryParams]="{ mine: true }">See all my reports</a>
          </div>
          @if (d.recent_reports.length) {
            <div class="cards">
              @for (item of d.recent_reports; track item.id) { <app-item-card [item]="item" /> }
            </div>
          } @else {
            <div class="empty">You have not reported anything yet. <a routerLink="/report">Report an item</a></div>
          }
        </section>

        <section class="panel" aria-labelledby="notes-heading">
          <div class="spread">
            <h2 id="notes-heading" style="margin: 0">Notifications</h2>
            @if (unread()) { <button class="btn btn-outline btn-sm" type="button" (click)="readAll()">Mark all as read</button> }
          </div>
          @if (!notifications().length) { <p class="muted" style="margin-top: 12px">No notifications yet.</p> }
          <ul class="list">
            @for (n of notifications(); track n.id) {
              <li [style.opacity]="n.read_at ? 0.7 : 1">
                <div class="spread">
                  <strong>{{ n.title }}</strong>
                  <span class="small muted">{{ n.created_at | date: 'medium' }}</span>
                </div>
                <p class="small" style="margin: 4px 0">{{ n.message }}</p>
                <div class="row small">
                  @if (n.item_id) { <a [routerLink]="['/items', n.item_id]">Open item</a> }
                  @if (!n.read_at) { <button class="link-btn" type="button" (click)="read(n)">Mark as read</button> }
                </div>
              </li>
            }
          </ul>
        </section>

        <div class="grid-2">
        <section class="panel" aria-labelledby="profile-heading">
          <h2 id="profile-heading">My details</h2>
          @if (auth.user(); as u) {
            <dl class="facts" style="margin-bottom: 16px">
              <dt>Email</dt><dd>{{ u.email }}</dd>
              <dt>SRM ID</dt><dd>{{ u.campus_id ?? 'Not set' }}</dd>
            </dl>
            <form (ngSubmit)="saveProfile()">
              <div class="field">
                <label for="profile-name">Full name</label>
                <input id="profile-name" name="profileName" required [(ngModel)]="profile.name" />
              </div>
              <div class="field">
                <label for="profile-department">Department</label>
                <input id="profile-department" name="profileDepartment" required minlength="2" maxlength="100" [(ngModel)]="profile.department" />
              </div>
              <div class="field">
                <label for="profile-phone">Phone <span class="hint">(optional)</span></label>
                <input id="profile-phone" name="profilePhone" type="tel" maxlength="20" [(ngModel)]="profile.phone" />
              </div>
              <button class="btn" type="submit">Save details</button>
              <p class="hint" style="margin-top: 8px">Your email and SRM ID cannot be changed here. Contact an administrator if they are wrong.</p>
            </form>
          }
        </section>

        <section class="panel" aria-labelledby="account-heading">
          <h2 id="account-heading">Change password</h2>
          <form (ngSubmit)="changePassword()">
            <div class="field">
              <label for="current-password">Current password</label>
              <input id="current-password" name="current" type="password" autocomplete="current-password" required [(ngModel)]="currentPassword" />
            </div>
            <div class="field">
              <label for="new-password">New password <span class="hint">(at least 12 characters)</span></label>
              <input id="new-password" name="new" type="password" autocomplete="new-password" minlength="12" required [(ngModel)]="newPassword" />
            </div>
            <button class="btn" type="submit">Change password</button>
            <p class="hint" style="margin-top: 8px">Other devices are signed out; this one stays signed in.</p>
          </form>
        </section>
        </div>
      }
    </div>
  `,
})
export class DashboardPage {
  protected readonly auth = inject(Auth);
  private readonly api = inject(Api);
  private readonly sanitizer = inject(DomSanitizer);
  protected readonly data = signal<UserDashboard | null>(null);
  protected readonly claims = signal<Claim[]>([]);
  protected readonly notifications = signal<Notification[]>([]);
  protected readonly unread = signal(0);
  protected readonly qr = signal<ShownQr | null>(null);
  protected readonly error = signal('');
  private readonly alerts = inject(Alerts);
  protected readonly claimLabels = CLAIM_LABELS;
  protected currentPassword = '';
  protected newPassword = '';
  protected profile = { name: '', department: '', phone: '' };

  constructor() {
    const user = this.auth.user();
    if (user) this.profile = { name: user.name, department: user.department ?? '', phone: user.phone ?? '' };
    this.refresh();
  }

  private refresh(): void {
    this.api.dashboard().subscribe({ next: (d) => this.data.set(d), error: (e) => this.error.set(errorMessage(e)) });
    this.api.myClaims().subscribe((c) => this.claims.set(c));
    this.api.notifications().subscribe((page) => {
      this.notifications.set(page.items);
      this.unread.set(page.unread);
    });
  }

  protected myItemId(match: Match): number {
    return match.counterpart.id === match.found_item_id ? match.lost_item_id : match.found_item_id;
  }

  protected showQr(claim: Claim): void {
    this.api.handoverQr(claim.id).subscribe({
      next: (code) => {
        // The SVG is generated by our own backend; it is shown as an image, never inserted as markup.
        const url = 'data:image/svg+xml;base64,' + btoa(code.svg);
        this.qr.set({ claimId: claim.id, image: this.sanitizer.bypassSecurityTrustUrl(url), expiresAt: code.expires_at });
      },
      error: (e) => this.alerts.error('Could not create the QR code', errorMessage(e)),
    });
  }

  protected withdraw(claim: Claim): void {
    if (!confirm(`Withdraw your claim for "${claim.item.title}"?`)) return;
    this.api.withdrawClaim(claim.id).subscribe({
      next: () => { this.alerts.success('Claim withdrawn.'); this.qr.set(null); this.refresh(); },
      error: (e) => this.alerts.error('Could not complete that', errorMessage(e)),
    });
  }

  protected saveProfile(): void {
    this.api.updateProfile({
      name: this.profile.name,
      department: this.profile.department,
      phone: this.profile.phone.trim() || null,
    }).subscribe({
      next: (user) => {
        this.auth.user.set(user);
        this.profile = { name: user.name, department: user.department ?? '', phone: user.phone ?? '' };
        this.alerts.success('Your details were saved.');
      },
      error: (e) => this.alerts.error('Your details were not saved', errorMessage(e)),
    });
  }

  protected changePassword(): void {
    this.api.changePassword(this.currentPassword, this.newPassword).subscribe({
      next: (r) => { this.alerts.success('Password changed', r.message); this.currentPassword = ''; this.newPassword = ''; },
      error: (e) => this.alerts.error('Password not changed', errorMessage(e)),
    });
  }

  protected read(n: Notification): void {
    this.api.markRead(n.id).subscribe(() => this.refresh());
  }

  protected readAll(): void {
    this.api.markAllRead().subscribe(() => this.refresh());
  }
}
