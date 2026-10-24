import { DOCUMENT } from '@angular/common';
import { Injectable, inject } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { ActivatedRouteSnapshot, NavigationEnd, NavigationStart, Router } from '@angular/router';
import { filter } from 'rxjs';

export const SITE_NAME = 'Campus Lost & Found Hub';
const DEFAULT_DESCRIPTION =
  'Report lost and found items on campus, see likely matches, and get your belongings back through a staff-verified handover.';

/** Route `data` read by Seo: title, description and noindex for private pages. */
export interface PageMeta {
  title?: string;
  description?: string;
  noindex?: boolean;
}

export interface Crumb {
  label: string;
  link?: string;
}

/** Keeps title, meta description, canonical link, robots and JSON-LD in sync with the current route. */
@Injectable({ providedIn: 'root' })
export class Seo {
  private readonly document = inject(DOCUMENT);
  private readonly title = inject(Title);
  private readonly meta = inject(Meta);
  private readonly router = inject(Router);

  init(): void {
    // Clear the previous page's structured data before the next page renders and adds its own.
    this.router.events.pipe(filter((event) => event instanceof NavigationStart)).subscribe(() => {
      this.setJsonLd('breadcrumbs', null);
      this.setJsonLd('page', null);
    });
    this.router.events.pipe(filter((event) => event instanceof NavigationEnd)).subscribe(() => {
      let snapshot: ActivatedRouteSnapshot = this.router.routerState.snapshot.root;
      while (snapshot.firstChild) snapshot = snapshot.firstChild;
      const data = snapshot.data as PageMeta;
      this.setPage(data.title, data.description ?? DEFAULT_DESCRIPTION);
      this.meta.updateTag({ name: 'robots', content: data.noindex ? 'noindex, nofollow' : 'index, follow' });
      this.setCanonical();
    });
  }

  /** Pages with dynamic titles (item detail) call this after loading. */
  setPage(title?: string, description?: string): void {
    this.title.setTitle(title ? `${title} | ${SITE_NAME}` : SITE_NAME);
    if (description) this.meta.updateTag({ name: 'description', content: description });
  }

  setBreadcrumbs(crumbs: Crumb[]): void {
    const origin = this.document.location.origin;
    this.setJsonLd('breadcrumbs', {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: crumbs.map((crumb, index) => ({
        '@type': 'ListItem',
        position: index + 1,
        name: crumb.label,
        ...(crumb.link ? { item: origin + crumb.link } : {}),
      })),
    });
  }

  setJsonLd(id: string, data: object | null): void {
    const scriptId = `jsonld-${id}`;
    this.document.getElementById(scriptId)?.remove();
    if (!data) return;
    const script = this.document.createElement('script');
    script.type = 'application/ld+json';
    script.id = scriptId;
    script.textContent = JSON.stringify(data);
    this.document.head.appendChild(script);
  }

  private setCanonical(): void {
    const path = this.router.url.split(/[?#]/)[0];
    let link = this.document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!link) {
      link = this.document.createElement('link');
      link.rel = 'canonical';
      this.document.head.appendChild(link);
    }
    link.href = this.document.location.origin + path;
  }
}
