import { DatePipe, DecimalPipe, PercentPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AccountStatus, AdminStats, Api, AuditLog, Reference, Role, User, errorMessage } from '../core/api';
import { Auth } from '../core/auth';
import { Alerts } from '../core/alerts';
import { Breadcrumbs } from '../shared/breadcrumbs';

type ReferenceKind = 'categories' | 'locations';

@Component({
  selector: 'app-admin',
  imports: [FormsModule, DatePipe, DecimalPipe, PercentPipe, Breadcrumbs],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page stack">
      <app-breadcrumbs [crumbs]="[{ label: 'Home', link: '/' }, { label: 'Administration' }]" />
      <h1>Administration</h1>

      @if (stats(); as s) {
        <section aria-labelledby="stats-heading" class="stack">
          <h2 id="stats-heading">Statistics</h2>
          <div class="stat-grid">
            <div class="stat"><span>Users</span><strong>{{ s.users.total }}</strong></div>
            <div class="stat lost"><span>Lost reports</span><strong>{{ sum(s.reports.LOST) }}</strong></div>
            <div class="stat found"><span>Found reports</span><strong>{{ sum(s.reports.FOUND) }}</strong></div>
            <div class="stat"><span>Found items returned</span>
              @if (s.found_return_rate === null) { <span class="muted small">None yet</span> } @else { <strong>{{ s.found_return_rate | percent: '1.0-0' }}</strong> }
            </div>
            <div class="stat"><span>Median time to return</span>
              @if (s.median_hours_to_return === null) { <span class="muted small">None yet</span> } @else { <strong>{{ s.median_hours_to_return | number: '1.0-1' }} h</strong> }
            </div>
          </div>
          <div class="grid-2">
            <div class="panel table-wrap">
              <h3>Reports by status</h3>
              <table>
                <thead><tr><th scope="col">Status</th><th scope="col">Lost</th><th scope="col">Found</th></tr></thead>
                <tbody>
                  @for (status of statuses; track status) {
                    <tr><td>{{ status }}</td><td>{{ s.reports.LOST[status] }}</td><td>{{ s.reports.FOUND[status] }}</td></tr>
                  }
                </tbody>
              </table>
            </div>
            <div class="panel table-wrap">
              <h3>Busiest categories</h3>
              @if (!s.by_category.length) { <p class="muted">No reports yet.</p> }
              <table>
                <thead><tr><th scope="col">Category</th><th scope="col">Lost</th><th scope="col">Found</th></tr></thead>
                <tbody>
                  @for (row of s.by_category.slice(0, 8); track row.id) {
                    <tr><td>{{ row.name }}</td><td>{{ row.lost }}</td><td>{{ row.found }}</td></tr>
                  }
                </tbody>
              </table>
            </div>
          </div>
        </section>
      }

      <section class="panel stack" aria-labelledby="users-heading">
        <h2 id="users-heading">Users</h2>
        <form class="search" (ngSubmit)="loadUsers()">
          <label class="sr-only" for="user-q">Search users</label>
          <input id="user-q" name="q" [(ngModel)]="userQuery" placeholder="Name or SRM email" />
          <button class="btn" type="submit">Search</button>
        </form>
        <div class="table-wrap">
          <table>
            <thead><tr><th scope="col">Name</th><th scope="col">Email</th><th scope="col">SRM ID</th><th scope="col">Department</th><th scope="col">Phone</th><th scope="col">Role</th><th scope="col">Account</th></tr></thead>
            <tbody>
              @for (u of users(); track u.id) {
                <tr>
                  <td>{{ u.name }}</td>
                  <td>{{ u.email }}</td>
                  <td>{{ u.campus_id ?? '' }}</td>
                  <td>{{ u.department ?? '' }}</td>
                  <td>{{ u.phone ?? '' }}</td>
                  <td>
                    <label class="sr-only" [for]="'role-' + u.id">Role for {{ u.name }}</label>
                    <select [id]="'role-' + u.id" [ngModel]="u.role" (ngModelChange)="setRole(u, $event)" [disabled]="u.id === auth.user()?.id" [name]="'role-' + u.id">
                      @for (r of roles; track r) { <option [value]="r">{{ r }}</option> }
                    </select>
                  </td>
                  <td>
                    <label class="sr-only" [for]="'status-' + u.id">Account status for {{ u.name }}</label>
                    <select [id]="'status-' + u.id" [ngModel]="u.account_status" (ngModelChange)="setStatus(u, $event)" [disabled]="u.id === auth.user()?.id" [name]="'status-' + u.id">
                      @for (a of accountStatuses; track a) { <option [value]="a">{{ a }}</option> }
                    </select>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>

      <div class="grid-2">
        @for (kind of kinds; track kind) {
          <section class="panel stack" [attr.aria-labelledby]="kind + '-heading'">
            <h2 [id]="kind + '-heading'">{{ kind === 'categories' ? 'Categories' : 'Campus places' }}</h2>
            <form class="search" (ngSubmit)="addReference(kind)">
              <label class="sr-only" [for]="'new-' + kind">New {{ kind === 'categories' ? 'category' : 'place' }}</label>
              <input [id]="'new-' + kind" [name]="'new-' + kind" [(ngModel)]="newNames[kind]" [placeholder]="kind === 'categories' ? 'New category' : 'New place'" />
              <button class="btn" type="submit">Add</button>
            </form>
            <ul class="list">
              @for (r of reference()[kind]; track r.id) {
                <li class="spread">
                  <span [class.muted]="!r.is_active">{{ r.name }} @if (!r.is_active) { <span class="small">(hidden)</span> }</span>
                  <button class="btn btn-outline btn-sm" type="button" (click)="toggle(kind, r)">{{ r.is_active ? 'Hide' : 'Show' }}</button>
                </li>
              }
            </ul>
          </section>
        }
      </div>

      <section class="panel table-wrap" aria-labelledby="audit-heading">
        <h2 id="audit-heading">Recent activity</h2>
        <table>
          <thead><tr><th scope="col">When</th><th scope="col">Who</th><th scope="col">Action</th><th scope="col">Record</th></tr></thead>
          <tbody>
            @for (log of audit(); track log.id) {
              <tr>
                <td>{{ log.created_at | date: 'short' }}</td>
                <td>{{ log.actor_email ?? 'System' }}</td>
                <td>{{ log.action }}</td>
                <td>{{ log.entity_type }} {{ log.entity_id ?? '' }}</td>
              </tr>
            }
          </tbody>
        </table>
      </section>
    </div>
  `,
})
export class AdminPage {
  protected readonly auth = inject(Auth);
  private readonly api = inject(Api);
  protected readonly stats = signal<AdminStats | null>(null);
  protected readonly users = signal<User[]>([]);
  protected readonly audit = signal<AuditLog[]>([]);
  protected readonly reference = signal<Record<ReferenceKind, Reference[]>>({ categories: [], locations: [] });
  private readonly alerts = inject(Alerts);
  protected readonly statuses = ['OPEN', 'MATCHED', 'CLAIMED', 'RETURNED', 'CLOSED'];
  protected readonly roles: Role[] = ['USER', 'STAFF', 'ADMIN'];
  protected readonly accountStatuses: AccountStatus[] = ['ACTIVE', 'SUSPENDED', 'DEACTIVATED'];
  protected readonly kinds: ReferenceKind[] = ['categories', 'locations'];
  protected newNames: Record<ReferenceKind, string> = { categories: '', locations: '' };
  protected userQuery = '';

  constructor() {
    this.api.adminStats().subscribe({ next: (s) => this.stats.set(s), error: this.fail });
    this.api.auditLogs().subscribe((page) => this.audit.set(page.items));
    this.loadUsers();
    this.kinds.forEach((kind) => this.loadReference(kind));
  }

  protected sum(counts: Record<string, number>): number {
    return Object.values(counts).reduce((a, b) => a + b, 0);
  }

  private fail = (e: unknown) => {
    this.alerts.error('Could not complete that', errorMessage(e));
  };

  private ok(message: string): void {
    this.alerts.success(message);
    this.api.auditLogs().subscribe((page) => this.audit.set(page.items));
  }

  protected loadUsers(): void {
    this.api.adminUsers(this.userQuery.trim()).subscribe({ next: (page) => this.users.set(page.items), error: this.fail });
  }

  protected setRole(user: User, role: Role): void {
    this.api.updateUser(user.id, { role }).subscribe({
      next: () => { this.ok(`${user.name} is now ${role}.`); this.loadUsers(); },
      error: (e) => { this.fail(e); this.loadUsers(); },
    });
  }

  protected setStatus(user: User, account_status: AccountStatus): void {
    this.api.updateUser(user.id, { account_status }).subscribe({
      next: () => { this.ok(`${user.name}'s account is now ${account_status}.`); this.loadUsers(); },
      error: (e) => { this.fail(e); this.loadUsers(); },
    });
  }

  private loadReference(kind: ReferenceKind): void {
    this.api.adminReference(kind).subscribe((rows) => this.reference.update((r) => ({ ...r, [kind]: rows })));
  }

  protected addReference(kind: ReferenceKind): void {
    const name = this.newNames[kind].trim();
    if (!name) return;
    this.api.createReference(kind, name).subscribe({
      next: () => { this.newNames[kind] = ''; this.ok(`Added ${name}.`); this.loadReference(kind); },
      error: this.fail,
    });
  }

  protected toggle(kind: ReferenceKind, row: Reference): void {
    this.api.updateReference(kind, row.id, { is_active: !row.is_active }).subscribe({
      next: () => { this.ok(`${row.name} is now ${row.is_active ? 'hidden from new reports' : 'available'}.`); this.loadReference(kind); },
      error: this.fail,
    });
  }
}
