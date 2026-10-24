import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { Api, Item, Match, errorMessage } from '../core/api';
import { Seo } from '../core/seo';
import { Alerts } from '../core/alerts';
import { Breadcrumbs } from '../shared/breadcrumbs';
import { StatusTag } from '../shared/status-tag';

const MAX_IMAGES = 5;

@Component({
  selector: 'app-item-detail',
  imports: [FormsModule, RouterLink, DatePipe, DecimalPipe, Breadcrumbs, StatusTag],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page">
      @if (item(); as it) {
        <app-breadcrumbs [crumbs]="[{ label: 'Home', link: '/' }, { label: 'Browse items', link: '/items' }, { label: it.title }]" />

        <div class="detail">
          <article class="stack">
            <app-status-tag [item]="it" />
            <h1>{{ it.title }}</h1>
            @if (it.images.length) {
              <div class="gallery">
                @for (image of it.images; track image.id; let i = $index) {
                  <img [src]="image.url" [alt]="'Photo ' + (i + 1) + ' of ' + it.title" />
                }
              </div>
            }
            <p style="white-space: pre-line">{{ it.description }}</p>
            <dl class="facts">
              <dt>Category</dt><dd>{{ it.category.name }}</dd>
              <dt>Place</dt><dd>{{ it.location.name }}</dd>
              <dt>{{ it.report_type === 'LOST' ? 'Lost on' : 'Found on' }}</dt><dd>{{ it.occurred_at | date: 'medium' }}</dd>
              @if (it.color) { <dt>Colour</dt><dd>{{ it.color }}</dd> }
              @if (it.brand) { <dt>Brand</dt><dd>{{ it.brand }}</dd> }
              <dt>Reported</dt><dd>{{ it.created_at | date: 'mediumDate' }}</dd>
            </dl>

            @if (it.is_owner && editable()) {
              <section class="panel stack" aria-labelledby="manage-heading">
                <h2 id="manage-heading">Manage your report</h2>
                @if (it.images.length < maxImages) {
                  <div>
                    <label for="photo">Add a photo <span class="hint">(JPEG, PNG or WebP, up to 5 MB)</span></label>
                    <input id="photo" type="file" accept="image/jpeg,image/png,image/webp" (change)="upload($event)" [disabled]="busy()" />
                  </div>
                }
                <div>
                  <button class="btn btn-danger" type="button" (click)="close()" [disabled]="busy()">
                    {{ it.report_type === 'LOST' ? 'I no longer need this report' : 'Close this report' }}
                  </button>
                </div>
              </section>
            }
          </article>

          <aside class="stack">
            @if (it.is_owner) {
              <section class="panel" aria-labelledby="matches-heading">
                <h2 id="matches-heading">Possible matches</h2>
                @if (!matches().length) {
                  <p class="muted">No suggestions yet. You will get a notification when a similar report appears.</p>
                }
                <ul class="list">
                  @for (m of matches(); track m.id) {
                    <li>
                      <div class="spread">
                        <a [routerLink]="['/items', m.counterpart.id]"><strong>{{ m.counterpart.title }}</strong></a>
                        <span class="tag tag-status">{{ m.score | number: '1.0-0' }}% similar</span>
                      </div>
                      <p class="small muted" style="margin: 4px 0">{{ m.counterpart.location.name }}, {{ m.counterpart.occurred_at | date: 'mediumDate' }}</p>
                      <details class="small">
                        <summary>Why this was suggested</summary>
                        <ul>
                          @for (r of m.reasons; track r.signal) { <li>{{ r.detail }}</li> }
                        </ul>
                      </details>
                      @if (m.status === 'SUGGESTED') {
                        <div class="row" style="margin-top: 8px">
                          @if (it.report_type === 'LOST') {
                            <button class="btn btn-sm" type="button" (click)="confirm(m)">This looks like mine</button>
                          }
                          <button class="btn btn-outline btn-sm" type="button" (click)="dismiss(m)">Not a match</button>
                        </div>
                      } @else {
                        <p class="small" style="margin: 8px 0 0">
                          Confirmed.
                          @if (it.report_type === 'LOST') {
                            <a [routerLink]="['/items', m.counterpart.id]">Open the found report</a> to submit a claim.
                          }
                        </p>
                      }
                    </li>
                  }
                </ul>
              </section>
            } @else if (it.report_type === 'FOUND' && editable()) {
              <section class="panel" aria-labelledby="claim-heading">
                <h2 id="claim-heading">Is this yours?</h2>
                @if (claimed()) {
                  <p>Your claim was sent to campus staff. Follow its progress on <a routerLink="/dashboard">your dashboard</a>.</p>
                } @else {
                  <p class="small muted">
                    Tell staff something only the owner would know, such as contents, marks or the lock screen.
                    Only staff see this. Do not repeat what is already in the listing.
                  </p>
                  <form (ngSubmit)="claim()">
                    <label for="evidence">Proof of ownership</label>
                    <textarea id="evidence" name="evidence" required minlength="20" maxlength="2000" [(ngModel)]="evidence"></textarea>
                    <button class="btn" type="submit" style="margin-top: 12px" [disabled]="busy()">Submit claim</button>
                  </form>
                }
              </section>
            } @else if (it.report_type === 'LOST' && editable()) {
              <section class="panel">
                <h2>Found this?</h2>
                <p class="small">Report it as found so the owner gets a match suggestion.</p>
                <a class="btn btn-found" routerLink="/report" [queryParams]="{ type: 'FOUND' }">I found something</a>
              </section>
            }
          </aside>
        </div>
      } @else if (error()) {
        <h1>Item not available</h1>
        <div class="alert alert-error" role="alert">{{ error() }}</div>
        <a routerLink="/items">Back to all items</a>
      }
    </div>
  `,
})
export class ItemDetailPage {
  readonly id = input.required<string>();
  private readonly api = inject(Api);
  private readonly seo = inject(Seo);
  protected readonly item = signal<Item | null>(null);
  protected readonly matches = signal<Match[]>([]);
  protected readonly error = signal('');
  private readonly alerts = inject(Alerts);
  protected readonly busy = signal(false);
  protected readonly claimed = signal(false);
  protected readonly maxImages = MAX_IMAGES;
  protected readonly editable = computed(() => ['OPEN', 'MATCHED'].includes(this.item()?.status ?? ''));
  protected evidence = '';

  constructor() {
    const state = inject(Router).currentNavigation()?.extras.state;
    if (typeof state?.['notice'] === 'string') {
      if (state['failed']) this.alerts.error('Some photos were not added', state['notice']);
      else this.alerts.success(state['notice']);
    }
    effect(() => this.load(Number(this.id())));
  }

  private load(id: number): void {
    this.api.item(id).subscribe({
      next: (item) => {
        this.item.set(item);
        this.seo.setPage(item.title, `${item.report_type === 'LOST' ? 'Lost' : 'Found'}: ${item.title} at ${item.location.name}.`);
        if (item.is_owner) this.api.itemMatches(id).subscribe((m) => this.matches.set(m));
      },
      error: (e) => this.error.set(errorMessage(e)),
    });
  }

  private run(action: () => void): void {
    this.busy.set(true);
    action();
  }

  private done = (message: string) => {
    this.busy.set(false);
    this.alerts.success(message);
    this.load(Number(this.id()));
  };

  private failed = (e: unknown) => {
    this.busy.set(false);
    this.alerts.error('Could not complete that', errorMessage(e));
  };

  protected upload(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.run(() => this.api.uploadImage(Number(this.id()), file).subscribe({
      next: () => { input.value = ''; this.done('Photo added. Location data was removed from it.'); },
      error: this.failed,
    }));
  }

  protected close(): void {
    if (!confirm('Close this report? It will no longer appear in searches.')) return;
    this.run(() => this.api.closeItem(Number(this.id())).subscribe({ next: () => this.done('Report closed.'), error: this.failed }));
  }

  protected claim(): void {
    this.run(() => this.api.submitClaim(Number(this.id()), this.evidence).subscribe({
      next: () => { this.busy.set(false); this.claimed.set(true); },
      error: this.failed,
    }));
  }

  protected confirm(match: Match): void {
    this.run(() => this.api.confirmMatch(match.id).subscribe({ next: () => this.done('Match confirmed. You can now claim the found item.'), error: this.failed }));
  }

  protected dismiss(match: Match): void {
    this.run(() => this.api.dismissMatch(match.id).subscribe({ next: () => this.done('Suggestion dismissed.'), error: this.failed }));
  }
}
