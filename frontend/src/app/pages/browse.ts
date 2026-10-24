import { ChangeDetectionStrategy, Component, effect, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { Api, Item, ItemQuery, Reference, errorMessage } from '../core/api';
import { Breadcrumbs } from '../shared/breadcrumbs';
import { Icon } from '../shared/icon';
import { ItemCard } from '../shared/item-card';

const PAGE_SIZE = 12;

@Component({
  selector: 'app-browse',
  imports: [FormsModule, Breadcrumbs, Icon, ItemCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page">
      <app-breadcrumbs [crumbs]="[{ label: 'Home', link: '/' }, { label: 'Browse items' }]" />
      <h1>{{ mine() ? 'My reports' : 'Browse lost and found items' }}</h1>

      <form class="filters" (ngSubmit)="apply()">
        <div>
          <label for="q">Keywords</label>
          <input id="q" name="q" [(ngModel)]="form.q" placeholder="Colour, brand, words in the description" />
        </div>
        <div>
          <label for="type">Type</label>
          <select id="type" name="type" [(ngModel)]="form.report_type">
            <option value="">Lost and found</option>
            <option value="LOST">Lost</option>
            <option value="FOUND">Found</option>
          </select>
        </div>
        <div>
          <label for="category">Category</label>
          <select id="category" name="category" [(ngModel)]="form.category_id">
            <option [ngValue]="null">Any category</option>
            @for (c of categories(); track c.id) { <option [ngValue]="c.id">{{ c.name }}</option> }
          </select>
        </div>
        <div>
          <label for="location">Place</label>
          <select id="location" name="location" [(ngModel)]="form.location_id">
            <option [ngValue]="null">Anywhere on campus</option>
            @for (l of locations(); track l.id) { <option [ngValue]="l.id">{{ l.name }}</option> }
          </select>
        </div>
        <div>
          <label for="sort">Sort by</label>
          <select id="sort" name="sort" [(ngModel)]="form.sort">
            <option value="newest">Newest reports</option>
            <option value="occurred_desc">Most recently lost or found</option>
            <option value="oldest">Oldest reports</option>
          </select>
        </div>
        <div><button class="btn" type="submit"><app-icon name="search" [size]="16" />Search</button></div>
      </form>

      @if (error()) { <div class="alert alert-error" role="alert">{{ error() }}</div> }
      @if (loaded()) {
        <p class="muted small" aria-live="polite">{{ total() }} {{ total() === 1 ? 'item' : 'items' }} found</p>
        @if (items().length) {
          <div class="cards">
            @for (item of items(); track item.id) { <app-item-card [item]="item" /> }
          </div>
          @if (pages() > 1) {
            <nav class="pagination" aria-label="Pages">
              <button class="btn btn-outline btn-sm" type="button" [disabled]="currentPage() <= 1" (click)="go(currentPage() - 1)">Previous</button>
              <span>Page {{ currentPage() }} of {{ pages() }}</span>
              <button class="btn btn-outline btn-sm" type="button" [disabled]="currentPage() >= pages()" (click)="go(currentPage() + 1)">Next</button>
            </nav>
          }
        } @else {
          <div class="empty">No reports match these filters. Try fewer keywords or a wider place.</div>
        }
      }
    </div>
  `,
})
export class BrowsePage {
  // Bound from query parameters so filters survive reloads and can be shared as links.
  readonly q = input<string>();
  readonly report_type = input<string>();
  readonly category_id = input<string>();
  readonly location_id = input<string>();
  readonly sort = input<string>();
  readonly page = input<string>();
  readonly mine = input<string>();

  private readonly api = inject(Api);
  private readonly router = inject(Router);
  protected readonly categories = signal<Reference[]>([]);
  protected readonly locations = signal<Reference[]>([]);
  protected readonly items = signal<Item[]>([]);
  protected readonly total = signal(0);
  protected readonly pages = signal(1);
  protected readonly currentPage = signal(1);
  protected readonly loaded = signal(false);
  protected readonly error = signal('');
  protected form: Required<Pick<ItemQuery, 'q' | 'report_type' | 'category_id' | 'location_id' | 'sort'>> = {
    q: '', report_type: '', category_id: null, location_id: null, sort: 'newest',
  };

  constructor() {
    this.api.categories().subscribe((c) => this.categories.set(c));
    this.api.locations().subscribe((l) => this.locations.set(l));
    effect(() => {
      const query: ItemQuery = {
        q: this.q() ?? '',
        report_type: (this.report_type() as ItemQuery['report_type']) ?? '',
        category_id: this.category_id() ? Number(this.category_id()) : null,
        location_id: this.location_id() ? Number(this.location_id()) : null,
        sort: this.sort() ?? 'newest',
        page: Math.max(1, Number(this.page() ?? 1) || 1),
        mine: this.mine() === 'true',
        page_size: PAGE_SIZE,
      };
      this.form = { q: query.q!, report_type: query.report_type!, category_id: query.category_id!, location_id: query.location_id!, sort: query.sort! };
      this.load(query);
    });
  }

  private load(query: ItemQuery): void {
    this.error.set('');
    this.api.items(query).subscribe({
      next: (result) => {
        this.items.set(result.items);
        this.total.set(result.total);
        this.currentPage.set(result.page);
        this.pages.set(Math.max(1, Math.ceil(result.total / PAGE_SIZE)));
        this.loaded.set(true);
      },
      error: (e) => { this.error.set(errorMessage(e)); this.loaded.set(true); },
    });
  }

  protected apply(): void {
    this.navigate({ ...this.form, page: null });
  }

  protected go(page: number): void {
    this.navigate({ page });
  }

  private navigate(changes: Record<string, unknown>): void {
    const queryParams: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(changes)) queryParams[key] = value === '' ? null : value;
    this.router.navigate(['/items'], { queryParams, queryParamsHandling: 'merge' });
  }
}
