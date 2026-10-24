import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { Api, Item, PublicStats } from '../core/api';
import { Auth } from '../core/auth';
import { SITE_NAME, Seo } from '../core/seo';
import { BeamsBackground } from '../shared/beams-background';
import { Icon } from '../shared/icon';
import { ItemCard } from '../shared/item-card';
import { JourneyTimeline } from '../shared/journey-timeline';

@Component({
  selector: 'app-home',
  imports: [FormsModule, RouterLink, BeamsBackground, Icon, ItemCard, JourneyTimeline],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-beams-background intensity="strong">
      <section class="container hero">
        <div class="hero-copy">
          <!-- Each line comes into focus in turn: the page's one authored entrance. -->
          <h1 class="hero-title">
            <span class="focus-in" style="--i: 0">Lost something on campus?</span>
            <span class="focus-in" style="--i: 1">Found something that isn't yours?</span>
          </h1>
          <p class="hero-lede rise-in" style="--i: 2">
            Post what you lost or found with a photo, the building and the date. Owners prove an item is theirs
            with a private claim, and the lost and found office hands it over after checking their SRM ID card.
          </p>
          <form class="hero-search rise-in" style="--i: 3" role="search" (ngSubmit)="search()">
            <label for="home-search">Search lost and found items</label>
            <div class="search">
              <input id="home-search" name="q" [(ngModel)]="query" placeholder="For example: blue water bottle library" />
              <button class="btn btn-on-dark" type="submit"><app-icon name="search" [size]="16" />Search</button>
            </div>
          </form>
          <div class="hero-actions rise-in" style="--i: 4">
            <a class="btn btn-lost" routerLink="/report" [queryParams]="{ type: 'LOST' }">I lost something</a>
            <a class="btn btn-found" routerLink="/report" [queryParams]="{ type: 'FOUND' }">I found something</a>
          </div>
        </div>

        @if (stats(); as s) {
          <aside class="listings rise-in" style="--i: 3" aria-labelledby="stats-heading">
            <h2 id="stats-heading">Listings right now</h2>
            <dl>
              <div class="listing lost"><dt>Open lost reports</dt><dd>{{ s.open_lost_reports }}</dd></div>
              <div class="listing found"><dt>Found items waiting for owners</dt><dd>{{ s.found_items_waiting }}</dd></div>
              <div class="listing returned"><dt>Items returned through this site</dt><dd>{{ s.items_returned }}</dd></div>
            </dl>
          </aside>
        }
      </section>
    </app-beams-background>

    <section class="band" aria-labelledby="recent-heading">
      <div class="container">
        <div class="section-head">
          <h2 id="recent-heading">Recently reported</h2>
          @if (auth.signedIn()) {
            <a routerLink="/items" class="arrow-link">See all items <app-icon name="arrow" [size]="16" /></a>
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
          <div class="cards stagger">
            @for (item of recent(); track item.id; let i = $index) {
              <app-item-card [item]="item" [style.--i]="i" />
            }
          </div>
        } @else if (recentLoaded()) {
          <div class="empty">Nothing has been reported yet. <a routerLink="/report">Report an item</a></div>
        }
      </div>
    </section>

    <section class="container page journey-section" aria-labelledby="how-heading">
      <div class="journey-intro">
        <h2 id="how-heading">From lost to found, in four steps</h2>
        <p class="muted">Every step keeps your proof private and the handover in person.</p>
      </div>
      <app-journey-timeline />
      <p class="small muted journey-foot">Read how your information is handled in the <a routerLink="/privacy">privacy policy</a>.</p>
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
