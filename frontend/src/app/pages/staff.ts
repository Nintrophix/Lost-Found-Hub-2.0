import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { Api, Claim, Handover, StaffDashboard, errorMessage } from '../core/api';
import { Alerts } from '../core/alerts';
import { Breadcrumbs } from '../shared/breadcrumbs';

@Component({
  selector: 'app-staff',
  imports: [FormsModule, RouterLink, DatePipe, Breadcrumbs],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page stack">
      <app-breadcrumbs [crumbs]="[{ label: 'Home', link: '/' }, { label: 'Staff desk' }]" />
      <h1>Staff desk</h1>

      @if (summary(); as s) {
        <div class="stat-grid">
          <div class="stat lost"><span>Claims to review</span><strong>{{ s.pending_claims }}</strong></div>
          <div class="stat"><span>Approved, no handover yet</span><strong>{{ s.approved_awaiting_handover }}</strong></div>
          <div class="stat"><span>Handovers ready</span><strong>{{ s.handovers['SCHEDULED'] }}</strong></div>
          <div class="stat found"><span>Returned in the last 7 days</span><strong>{{ s.completed_last_7_days }}</strong></div>
        </div>
      }

      <section class="panel stack" aria-labelledby="scan-heading">
        <h2 id="scan-heading">Hand over an item</h2>
        <form class="search" (ngSubmit)="verify()">
          <label class="sr-only" for="payload">QR code text</label>
          <input id="payload" name="payload" [(ngModel)]="payload" autocomplete="off"
                 placeholder="Scan the claimant's QR code (or paste its text)" />
          <button class="btn" type="submit" [disabled]="!payload.trim()">Check code</button>
        </form>
        <p class="hint">A code works once and expires after 15 minutes. A valid code is not proof of ownership on its own: check the person's SRM ID card.</p>

        @if (verified(); as h) {
          <div class="panel stack" style="background: var(--soft)">
            <h3>Code accepted for "{{ h.item_title }}"</h3>
            <dl class="facts">
              <dt>Claimant</dt><dd>{{ h.claimant.name }}</dd>
              <dt>SRM ID</dt><dd>{{ h.claimant.campus_id ?? 'Not on record' }}</dd>
              <dt>Email</dt><dd>{{ h.claimant.email }}</dd>
            </dl>
            <label class="choice"><input type="checkbox" name="idChecked" [(ngModel)]="idChecked" /> I checked their SRM ID card and the name and ID match</label>
            <div>
              <label for="notes">Notes <span class="hint">(optional)</span></label>
              <input id="notes" name="notes" [(ngModel)]="notes" />
            </div>
            <div class="row">
              <button class="btn btn-found" type="button" [disabled]="!idChecked" (click)="complete(h)">Complete handover</button>
              <button class="btn btn-danger" type="button" (click)="cancel(h)">Cancel handover</button>
            </div>
          </div>
        }
      </section>

      <section class="panel" aria-labelledby="review-heading">
        <h2 id="review-heading">Claims waiting for review</h2>
        @if (!pending().length) { <p class="muted">Nothing to review.</p> }
        <ul class="list">
          @for (c of pending(); track c.id) {
            <li class="stack">
              <div class="spread">
                <a [routerLink]="['/items', c.item.id]"><strong>{{ c.item.title }}</strong></a>
                <span class="small muted">Submitted {{ c.created_at | date: 'medium' }}</span>
              </div>
              <p class="small" style="margin: 0">Claimant: {{ c.claimant?.name }}, {{ c.claimant?.campus_id ?? 'no SRM ID' }} ({{ c.claimant?.email }})</p>
              <blockquote class="panel small" style="margin: 0; white-space: pre-line">{{ c.evidence }}</blockquote>
              <div>
                <label [for]="'reason-' + c.id">Note to the claimant <span class="hint">(required to reject)</span></label>
                <input [id]="'reason-' + c.id" [(ngModel)]="reasons[c.id]" [name]="'reason-' + c.id" />
              </div>
              <div class="row">
                <button class="btn btn-found btn-sm" type="button" (click)="approve(c)">Approve</button>
                <button class="btn btn-danger btn-sm" type="button" (click)="reject(c)">Reject</button>
              </div>
            </li>
          }
        </ul>
      </section>

      <section class="panel" aria-labelledby="approved-heading">
        <h2 id="approved-heading">Approved, waiting for a handover</h2>
        @if (!approved().length) { <p class="muted">No approved claims are waiting.</p> }
        <ul class="list">
          @for (c of approved(); track c.id) {
            <li class="spread">
              <span><a [routerLink]="['/items', c.item.id]">{{ c.item.title }}</a> <span class="small muted">for {{ c.claimant?.name }}</span></span>
              <button class="btn btn-sm" type="button" (click)="schedule(c)">Ready for collection</button>
            </li>
          }
        </ul>
      </section>

      <section class="panel" aria-labelledby="handovers-heading">
        <h2 id="handovers-heading">Handovers in progress</h2>
        @if (!handovers().length) { <p class="muted">No handovers in progress.</p> }
        <ul class="list">
          @for (h of handovers(); track h.id) {
            <li class="spread">
              <span>{{ h.item_title }} <span class="small muted">for {{ h.claimant.name }}, {{ h.status === 'VERIFIED' ? 'code scanned' : 'waiting for the claimant' }}</span></span>
              <span class="row">
                @if (h.status === 'VERIFIED') { <button class="btn btn-sm" type="button" (click)="resume(h)">Finish</button> }
                <button class="btn btn-danger btn-sm" type="button" (click)="cancel(h)">Cancel</button>
              </span>
            </li>
          }
        </ul>
      </section>
    </div>
  `,
})
export class StaffPage {
  private readonly api = inject(Api);
  protected readonly summary = signal<StaffDashboard | null>(null);
  protected readonly pending = signal<Claim[]>([]);
  protected readonly approved = signal<Claim[]>([]);
  protected readonly handovers = signal<Handover[]>([]);
  protected readonly verified = signal<Handover | null>(null);
  private readonly alerts = inject(Alerts);
  protected reasons: Record<number, string> = {};
  protected payload = '';
  protected idChecked = false;
  protected notes = '';

  constructor() {
    this.refresh();
  }

  private refresh(): void {
    this.api.staffDashboard().subscribe((s) => this.summary.set(s));
    this.api.staffClaims('PENDING').subscribe((page) => this.pending.set(page.items));
    this.api.staffClaims('APPROVED').subscribe((page) =>
      this.approved.set(page.items.filter((c) => !c.handover || c.handover.status === 'CANCELLED')),
    );
    forkJoin([this.api.handovers('SCHEDULED'), this.api.handovers('VERIFIED')]).subscribe(([scheduled, verified]) =>
      this.handovers.set([...verified.items, ...scheduled.items]),
    );
  }

  private ok = (message: string) => {
    this.alerts.success(message);
    this.refresh();
  };

  private fail = (e: unknown) => {
    this.alerts.error('Could not complete that', errorMessage(e));
  };

  protected approve(claim: Claim): void {
    this.api.approveClaim(claim.id, this.reasons[claim.id]?.trim() || null).subscribe({
      next: () => this.ok(`Claim for "${claim.item.title}" approved. Mark it ready for collection when you have the item.`),
      error: this.fail,
    });
  }

  protected reject(claim: Claim): void {
    const reason = this.reasons[claim.id]?.trim();
    if (!reason) {
      this.alerts.error('Add a note first', 'Write a note explaining why the claim was rejected.');
      return;
    }
    this.api.rejectClaim(claim.id, reason).subscribe({ next: () => this.ok('Claim rejected and the claimant notified.'), error: this.fail });
  }

  protected schedule(claim: Claim): void {
    this.api.scheduleHandover(claim.id, null).subscribe({
      next: () => this.ok(`${claim.claimant?.name} can now show their QR code to collect "${claim.item.title}".`),
      error: this.fail,
    });
  }

  protected verify(): void {
    this.api.verifyHandover(this.payload.trim()).subscribe({
      next: (h) => { this.resume(h); this.payload = ''; this.refresh(); },
      error: (e) => { this.verified.set(null); this.fail(e); },
    });
  }

  protected resume(handover: Handover): void {
    this.idChecked = false;
    this.notes = '';
    this.verified.set(handover);
  }

  protected complete(handover: Handover): void {
    this.api.completeHandover(handover.id, this.notes.trim() || null).subscribe({
      next: () => { this.verified.set(null); this.ok(`"${handover.item_title}" was handed over to ${handover.claimant.name}.`); },
      error: this.fail,
    });
  }

  protected cancel(handover: Handover): void {
    const reason = prompt('Why is this handover being cancelled? (at least 5 characters)');
    if (!reason || reason.trim().length < 5) return;
    this.api.cancelHandover(handover.id, reason.trim()).subscribe({
      next: () => { this.verified.set(null); this.ok('Handover cancelled. The claim stays approved.'); },
      error: this.fail,
    });
  }
}
