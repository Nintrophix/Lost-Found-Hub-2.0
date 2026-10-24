import { DOCUMENT } from '@angular/common';
import { Injectable, effect, inject } from '@angular/core';
import { Router } from '@angular/router';

import { Api, Notification } from './api';
import { Alerts } from './alerts';
import { Auth } from './auth';

const POLL_MS = 60_000;
const MAX_AT_ONCE = 3;

/**
 * Shows new unread notifications in the alert stack while someone is signed in. Polls once a minute,
 * skips while the tab is hidden, and never shows the same notification twice in a visit.
 */
@Injectable({ providedIn: 'root' })
export class NotificationFeed {
  private readonly api = inject(Api);
  private readonly alerts = inject(Alerts);
  private readonly auth = inject(Auth);
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);
  private readonly seen = new Set<number>();
  private timer: ReturnType<typeof setInterval> | null = null;

  start(): void {
    effect(() => {
      if (this.auth.signedIn()) {
        this.check();
        this.timer ??= setInterval(() => this.check(), POLL_MS);
      } else {
        if (this.timer) clearInterval(this.timer);
        this.timer = null;
        this.seen.clear();
      }
    });
    this.document.addEventListener('visibilitychange', () => {
      if (this.document.visibilityState === 'visible' && this.auth.signedIn()) this.check();
    });
  }

  /** Re-check now, e.g. after an action that may have created a notification. */
  check(): void {
    if (this.document.visibilityState === 'hidden') return;
    this.api.notifications().subscribe({
      next: (page) => this.show(page.items.filter((n) => !n.read_at && !this.seen.has(n.id))),
      error: () => undefined, // A missed poll is harmless; the next one catches up.
    });
  }

  private show(fresh: Notification[]): void {
    fresh.forEach((n) => this.seen.add(n.id));
    // Oldest first so the newest ends up on top of the stack.
    for (const n of fresh.slice(0, MAX_AT_ONCE).reverse()) {
      this.alerts.info({
        title: n.title,
        message: n.message,
        actions: [
          ...(n.item_id ? [{ label: 'Open item', run: () => this.router.navigate(['/items', n.item_id]) }] : []),
          { label: 'Mark as read', run: () => this.api.markRead(n.id).subscribe() },
        ],
      });
    }
    if (fresh.length > MAX_AT_ONCE) {
      this.alerts.info({
        title: `${fresh.length - MAX_AT_ONCE} more unread notifications`,
        actions: [{ label: 'Open dashboard', run: () => this.router.navigate(['/dashboard']) }],
      });
    }
  }
}
