import { ChangeDetectionStrategy, Component, OnDestroy, effect, inject } from '@angular/core';

import { Alert, Alerts } from '../core/alerts';
import { Icon } from './icon';

const ICONS: Record<Alert['kind'], string> = { success: 'check', error: 'alert', info: 'bell' };

/**
 * Stack of dismissible alerts. Timed alerts pause while hovered or focused, so they never vanish
 * while someone is reading or reaching for a button. Errors are announced assertively.
 */
@Component({
  selector: 'app-alert-stack',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="alert-stack" aria-label="Notifications">
      @for (alert of alerts.items(); track alert.id) {
        <div [class]="'toast toast-' + alert.kind" [attr.role]="alert.kind === 'error' ? 'alert' : 'status'"
             (mouseenter)="pause(alert)" (mouseleave)="resume(alert)" (focusin)="pause(alert)" (focusout)="resume(alert)">
          <span class="toast-icon"><app-icon [name]="icons[alert.kind]" [size]="18" /></span>
          <div class="toast-body">
            <p class="toast-title">{{ alert.title }}</p>
            @if (alert.message) { <p class="toast-message">{{ alert.message }}</p> }
            @if (alert.actions.length) {
              <div class="toast-actions">
                @for (action of alert.actions; track action.label) {
                  <button type="button" class="link-btn" (click)="act(alert, action.run)">{{ action.label }}</button>
                }
              </div>
            }
          </div>
          <button type="button" class="toast-close" (click)="alerts.dismiss(alert.id)" [attr.aria-label]="'Dismiss: ' + alert.title">
            <app-icon name="close" [size]="16" />
          </button>
          @if (alert.timeout) {
            <span class="toast-timer" [style.animation-duration.ms]="alert.timeout" [class.paused]="paused.has(alert.id)"></span>
          }
        </div>
      }
    </section>
  `,
})
export class AlertStack implements OnDestroy {
  protected readonly alerts = inject(Alerts);
  protected readonly icons = ICONS;
  protected readonly paused = new Set<number>();
  // Remaining time per timed alert, so pausing and resuming keeps the countdown honest.
  private readonly remaining = new Map<number, number>();
  private readonly timers = new Map<number, { handle: ReturnType<typeof setTimeout>; started: number }>();

  constructor() {
    effect(() => {
      const live = new Set<number>();
      for (const alert of this.alerts.items()) {
        live.add(alert.id);
        if (alert.timeout && !this.remaining.has(alert.id)) {
          this.remaining.set(alert.id, alert.timeout);
          this.start(alert.id);
        }
      }
      for (const id of [...this.remaining.keys()]) {
        if (!live.has(id)) this.forget(id);
      }
    });
  }

  protected pause(alert: Alert): void {
    const timer = this.timers.get(alert.id);
    if (!timer) return;
    clearTimeout(timer.handle);
    this.timers.delete(alert.id);
    this.remaining.set(alert.id, Math.max(0, (this.remaining.get(alert.id) ?? 0) - (Date.now() - timer.started)));
    this.paused.add(alert.id);
  }

  protected resume(alert: Alert): void {
    if (!this.paused.delete(alert.id)) return;
    this.start(alert.id);
  }

  protected act(alert: Alert, run: () => void): void {
    run();
    this.alerts.dismiss(alert.id);
  }

  private start(id: number): void {
    const ms = this.remaining.get(id) ?? 0;
    this.timers.set(id, { handle: setTimeout(() => this.alerts.dismiss(id), ms), started: Date.now() });
  }

  private forget(id: number): void {
    const timer = this.timers.get(id);
    if (timer) clearTimeout(timer.handle);
    this.timers.delete(id);
    this.remaining.delete(id);
    this.paused.delete(id);
  }

  ngOnDestroy(): void {
    for (const id of [...this.timers.keys()]) this.forget(id);
  }
}
