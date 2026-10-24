import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { catchError, concatMap, from, map, of, switchMap, toArray } from 'rxjs';

import { Api, ReportType, Reference, errorMessage } from '../core/api';
import { Breadcrumbs } from '../shared/breadcrumbs';

const MAX_PHOTOS = 5;
const MAX_BYTES = 5 * 1024 * 1024;

/** Value for <input type="datetime-local"> in the browser's own time zone. */
function localInputValue(date: Date): string {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

@Component({
  selector: 'app-report',
  imports: [FormsModule, Breadcrumbs],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page">
      <app-breadcrumbs [crumbs]="[{ label: 'Home', link: '/' }, { label: 'Report an item' }]" />
      <div style="max-width: 640px">
        <h1>Report an item</h1>
        @if (error()) { <div class="alert alert-error" role="alert">{{ error() }}</div> }

        <form (ngSubmit)="submit()">
          <fieldset class="field" style="border: 0; padding: 0; margin: 0 0 16px">
            <legend style="font-weight: 600; color: var(--ink); margin-bottom: 6px">What happened?</legend>
            <div class="row">
              <label class="choice"><input type="radio" name="type" value="LOST" [(ngModel)]="reportType" /> I lost something</label>
              <label class="choice"><input type="radio" name="type" value="FOUND" [(ngModel)]="reportType" /> I found something</label>
            </div>
          </fieldset>

          <div class="field">
            <label for="title">Short title <span class="hint">(for example: Black Pixel phone)</span></label>
            <input id="title" name="title" required minlength="3" maxlength="150" [(ngModel)]="title" />
          </div>
          <div class="field">
            <label for="description">Description</label>
            <textarea id="description" name="description" required minlength="10" maxlength="2000" [(ngModel)]="description"></textarea>
            @if (reportType === 'FOUND') {
              <p class="hint" style="margin: 6px 0 0">Leave out details only the owner would know, such as contents or a lock screen. Staff use those to check claims.</p>
            }
          </div>
          <div class="grid-2" style="gap: 16px">
            <div class="field">
              <label for="category">Category</label>
              <select id="category" name="category" required [(ngModel)]="categoryId">
                <option [ngValue]="null" disabled>Choose a category</option>
                @for (c of categories(); track c.id) { <option [ngValue]="c.id">{{ c.name }}</option> }
              </select>
            </div>
            <div class="field">
              <label for="location">Where</label>
              <select id="location" name="location" required [(ngModel)]="locationId">
                <option [ngValue]="null" disabled>Choose a place</option>
                @for (l of locations(); track l.id) { <option [ngValue]="l.id">{{ l.name }}</option> }
              </select>
            </div>
            <div class="field">
              <label for="occurred">{{ reportType === 'LOST' ? 'When you lost it' : 'When you found it' }}</label>
              <input id="occurred" name="occurred" type="datetime-local" required [max]="now" [(ngModel)]="occurredAt" />
            </div>
            <div class="field">
              <label for="color">Colour <span class="hint">(optional)</span></label>
              <input id="color" name="color" maxlength="40" [(ngModel)]="color" />
            </div>
            <div class="field">
              <label for="brand">Brand <span class="hint">(optional)</span></label>
              <input id="brand" name="brand" maxlength="80" [(ngModel)]="brand" />
            </div>
          </div>
          <div class="field">
            <label for="photos">Photos <span class="hint">(optional, up to {{ maxPhotos }}, JPEG, PNG or WebP, 5 MB each)</span></label>
            <input id="photos" type="file" multiple accept="image/jpeg,image/png,image/webp" (change)="pick($event)" />
            @if (photos().length) {
              <p class="hint" style="margin: 6px 0 0">{{ photos().length }} selected. Location data is removed from photos when they are saved.</p>
            }
          </div>
          <button class="btn" type="submit" [class.btn-lost]="reportType === 'LOST'" [class.btn-found]="reportType === 'FOUND'" [disabled]="busy()">
            {{ busy() ? 'Saving...' : 'Submit report' }}
          </button>
        </form>
      </div>
    </div>
  `,
})
export class ReportPage implements OnInit {
  readonly type = input<string>();
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  protected readonly categories = signal<Reference[]>([]);
  protected readonly locations = signal<Reference[]>([]);
  protected readonly photos = signal<File[]>([]);
  protected readonly error = signal('');
  protected readonly busy = signal(false);
  protected readonly maxPhotos = MAX_PHOTOS;
  protected readonly now = localInputValue(new Date());

  protected reportType: ReportType = 'LOST';
  protected title = '';
  protected description = '';
  protected categoryId: number | null = null;
  protected locationId: number | null = null;
  protected occurredAt = this.now;
  protected color = '';
  protected brand = '';

  constructor() {
    this.api.categories().subscribe((c) => this.categories.set(c));
    this.api.locations().subscribe((l) => this.locations.set(l));
  }

  ngOnInit(): void {
    if (this.type() === 'FOUND') this.reportType = 'FOUND';
  }

  protected pick(event: Event): void {
    const files = Array.from((event.target as HTMLInputElement).files ?? []);
    this.error.set('');
    if (files.length > MAX_PHOTOS) {
      this.error.set(`Choose at most ${MAX_PHOTOS} photos.`);
    } else if (files.some((f) => f.size > MAX_BYTES)) {
      this.error.set('Each photo must be 5 MB or smaller.');
    } else {
      this.photos.set(files);
      return;
    }
    (event.target as HTMLInputElement).value = '';
    this.photos.set([]);
  }

  protected submit(): void {
    if (this.categoryId === null || this.locationId === null) {
      this.error.set('Choose a category and a place.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.api
      .createItem({
        report_type: this.reportType,
        title: this.title,
        description: this.description,
        category_id: this.categoryId,
        location_id: this.locationId,
        occurred_at: new Date(this.occurredAt).toISOString(),
        color: this.color || null,
        brand: this.brand || null,
      })
      .pipe(
        // The report is saved first. A failed photo must not look like a failed report (the user
        // would resubmit and create a duplicate), so upload errors are collected and shown on the report.
        switchMap((item) =>
          from(this.photos()).pipe(
            concatMap((file) =>
              this.api.uploadImage(item.id, file).pipe(
                map(() => null),
                catchError((e) => of(`${file.name}: ${errorMessage(e)}`)),
              ),
            ),
            toArray(),
            map((results) => ({ item, failures: results.filter((r): r is string => r !== null) })),
          ),
        ),
      )
      .subscribe({
        next: ({ item, failures }) => {
          const notice = failures.length
            ? `Your report was saved. ${failures.join(' ')} You can add photos again below.`
            : 'Report saved.';
          this.router.navigate(['/items', item.id], { state: { notice, failed: failures.length > 0 } });
        },
        error: (e) => { this.error.set(errorMessage(e)); this.busy.set(false); },
      });
  }
}
