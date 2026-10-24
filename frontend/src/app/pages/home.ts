import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { Api, Item, PublicStats } from '../core/api';
import { Auth } from '../core/auth';
import { SITE_NAME, Seo } from '../core/seo';
import { BeamsBackground } from '../shared/beams-background';
import { Icon } from '../shared/icon';
import { ItemCard } from '../shared/item-card';

@Component({
  selector: 'app-home',
  imports: [FormsModule, RouterLink, BeamsBackground, Icon, ItemCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-beams-background intensity="strong">
    <section class="container hero" style="padding-block: 40px 48px">
      <div>
        <h1>Lost something on campus? Found something that isn't yours?</h1>
        <p>
          Post what you lost or found with a photo, the building and the date. Owners prove an item is theirs
          with a private claim, and campus staff hand it over after checking their SRM ID card.
        </p>
        <form class="search" role="search" (ngSubmit)="search()">
          <div style="flex: 1">
            <label for="home-search">Search lost and found items</label>
            <div class="search">
              <input id="home-search" name="q" [(ngModel)]="query" placeholder="For example: blue water bottle library" />
              <button class="btn" type="submit"><app-icon name="search" [size]="16" />Search</button>
            </div>
          </div>
        </form>
        <div class="hero-actions">
          <a class="btn btn-lost" routerLink="/report" [queryParams]="{ type: 'LOST' }">I lost something</a>
          <a class="btn btn-found" routerLink="/report" [queryParams]="{ type: 'FOUND' }">I found something</a>
        </div>
      </div>

      @if (stats(); as s) {
        <aside aria-labelledby="stats-heading">
          <h2 id="stats-heading" style="font-size: 1rem">Listings right now</h2>
          <div class="stat lost"><span>Open lost reports</span><strong>{{ s.open_lost_reports }}</strong></div>
          <div class="stat found"><span>Found items waiting for owners</span><strong>{{ s.found_items_waiting }}</strong></div>
          <div class="stat"><span>Items returned through this site</span><strong>{{ s.items_returned }}</strong></div>
        </aside>
      }
    </section>
    </app-beams-background>

    <section class="band" aria-labelledby="recent-heading">
      <div class="container">
        <div class="spread" style="margin-bottom: 16px">
          <h2 id="recent-heading" style="margin: 0">Recently reported</h2>
          @if (auth.signedIn()) {
            <a routerLink="/items" class="row" style="gap: 4px">See all items <app-icon name="arrow" [size]="16" /></a>
          }
        </div>
        @if (!auth.signedIn()) {
          <div class="empty">
            <p>Reports are visible only to signed-in members of SRM, using a {{ auth.domainHint() }} email address.</p>
            <div class="row" style="justify-content: center">
              <a class="btn" routerLink="/login">Log in</a>
              <a class="btn btn-outline" routerLink="/register">Create account</a>
            </div>
          </div>
        } @else if (recent().length) {
          <div class="cards">
            @for (item of recent(); track item.id) {
              <app-item-card [item]="item" />
            }
          </div>
        } @else if (recentLoaded()) {
          <div class="empty">Nothing has been reported yet. <a routerLink="/report">Report an item</a></div>
        }
      </div>
    </section>

    <section class="container page" aria-labelledby="how-heading">
      <h2 id="how-heading">How it works</h2>
      <div class="grid-2">
        <div>
          <h3>1. Report it</h3>
          <p>Describe the item, where and when. Photos are stripped of location data before they are stored.</p>
        </div>
        <div>
          <h3>2. Check suggested matches</h3>
          <p>Reports are compared by category, description, colour, place and date. Suggestions are only a starting point.</p>
        </div>
        <div>
          <h3>3. Claim and collect</h3>
          <p>Tell staff privately what proves it is yours. Once approved, show the QR code from your dashboard at the desk.</p>
        </div>
      </div>
      <p class="small muted">Read how your information is handled in the <a routerLink="/privacy">privacy policy</a>.</p>
    </section>
  `,
})
export class HomePage {
  protected readonly auth = inject(Auth);
  private readonly api = inject(Api);
  private readonly router = inject(Router);
  protected readonly stats = signal<PublicStats | null>(null);
  protected readonly recent = signal<Item[]>([]);
  protected readonly recentLoaded = signal(false);
  protected query = '';

  constructor() {
    const seo = inject(Seo);
    const origin = document.location.origin;
    seo.setJsonLd('page', {
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: SITE_NAME,
      url: origin + '/',
      potentialAction: {
        '@type': 'SearchAction',
        target: `${origin}/items?q={search_term_string}`,
        'query-input': 'required name=search_term_string',
      },
    });
    // If the counts cannot be loaded the panel is simply not shown; numbers are never invented.
    this.api.publicStats().subscribe({ next: (s) => this.stats.set(s), error: () => this.stats.set(null) });
    if (this.auth.signedIn()) {
      this.api.items({ page_size: 4 }).subscribe({
        next: (page) => { this.recent.set(page.items); this.recentLoaded.set(true); },
        error: () => this.recentLoaded.set(true),
      });
    }
  }

  protected search(): void {
    const q = this.query.trim();
    this.router.navigate(['/items'], { queryParams: q ? { q } : {} });
  }
}
