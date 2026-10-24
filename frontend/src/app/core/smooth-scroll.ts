import { DOCUMENT } from '@angular/common';
import { Injectable, NgZone, inject } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import Lenis from 'lenis';
import { filter } from 'rxjs';

/**
 * Inertial smooth scrolling for mouse and trackpad (Lenis). Native scrolling is kept for touch
 * screens, where the platform's own physics are better, and for reduced-motion users.
 * Lenis drives the real window scroll position, so scroll events, sticky elements and the
 * journey timeline keep working unchanged.
 */
@Injectable({ providedIn: 'root' })
export class SmoothScroll {
  private readonly document = inject(DOCUMENT);
  private readonly router = inject(Router);
  private readonly zone = inject(NgZone);
  private lenis: Lenis | null = null;

  start(): void {
    const view = this.document.defaultView;
    if (!view || typeof view.matchMedia !== 'function') return;
    const fine = view.matchMedia('(pointer: fine)').matches;
    const reduced = view.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!fine || reduced) return;

    this.zone.runOutsideAngular(() => {
      this.lenis = new Lenis({ autoRaf: true, duration: 1.05, easing: (t) => 1 - Math.pow(1 - t, 4), smoothWheel: true });
    });

    // A new page starts at the top immediately, never with a glide from the previous page's position.
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe(() => {
      this.lenis?.scrollTo(0, { immediate: true, force: true });
    });
  }

  /** Smoothly bring an element into view (falls back to native smooth scrolling). */
  scrollTo(target: HTMLElement): void {
    if (this.lenis) this.lenis.scrollTo(target, { offset: -80 });
    else target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}
