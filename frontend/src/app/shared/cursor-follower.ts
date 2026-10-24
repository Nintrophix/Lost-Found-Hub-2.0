import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, ElementRef, NgZone, OnDestroy, OnInit, inject } from '@angular/core';

const INTERACTIVE = 'a, button, input, select, textarea, label, summary, [role="menuitem"], [tabindex]:not([tabindex="-1"])';
const EASE = 0.2; // Share of the remaining distance covered per frame.

/**
 * Decorative ring that trails the pointer and grows over interactive elements. The native cursor
 * stays visible, so nothing depends on this. Only runs with a precise pointer (mouse or trackpad)
 * and when the user has not asked for reduced motion; the loop stops whenever the ring is at rest.
 */
@Component({
  selector: 'app-cursor-follower',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div class="cursor-ring" aria-hidden="true"></div>`,
})
export class CursorFollower implements OnInit, OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly zone = inject(NgZone);
  private readonly ring = inject<ElementRef<HTMLElement>>(ElementRef);
  private target = { x: -100, y: -100 };
  private position = { x: -100, y: -100 };
  private frame = 0;
  private enabled = false;
  private readonly listeners: [string, EventListener][] = [];

  ngOnInit(): void {
    const view = this.document.defaultView;
    // Purely decorative: if the browser cannot tell us about the pointer or motion settings, skip it.
    if (!view || typeof view.matchMedia !== 'function') return;
    const fine = view.matchMedia('(pointer: fine)').matches;
    const reduced = view.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!fine || reduced) return;
    this.enabled = true;
    this.zone.runOutsideAngular(() => {
      this.listen('pointermove', (e) => {
        const event = e as PointerEvent;
        this.target = { x: event.clientX, y: event.clientY };
        const el = this.element();
        el.classList.add('visible');
        el.classList.toggle('over-interactive', !!(event.target as Element | null)?.closest?.(INTERACTIVE));
        this.run();
      });
      this.listen('pointerdown', () => this.element().classList.add('pressed'));
      this.listen('pointerup', () => this.element().classList.remove('pressed'));
      this.listen('pointerleave', () => this.element().classList.remove('visible'));
    });
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.frame);
    for (const [type, fn] of this.listeners) this.document.documentElement.removeEventListener(type, fn);
  }

  private element(): HTMLElement {
    return this.ring.nativeElement.firstElementChild as HTMLElement;
  }

  private listen(type: string, fn: EventListener): void {
    this.document.documentElement.addEventListener(type, fn, { passive: true });
    this.listeners.push([type, fn]);
  }

  private run(): void {
    if (this.enabled && !this.frame) this.frame = requestAnimationFrame(this.step);
  }

  private readonly step = () => {
    this.position.x += (this.target.x - this.position.x) * EASE;
    this.position.y += (this.target.y - this.position.y) * EASE;
    this.element().style.transform = `translate3d(${this.position.x}px, ${this.position.y}px, 0)`;
    const resting = Math.abs(this.target.x - this.position.x) < 0.1 && Math.abs(this.target.y - this.position.y) < 0.1;
    this.frame = resting ? 0 : requestAnimationFrame(this.step);
  };
}
