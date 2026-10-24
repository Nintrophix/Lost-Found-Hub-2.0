import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, ElementRef, NgZone, OnDestroy, OnInit, inject, viewChild } from '@angular/core';

// Angular port of the fluid magnetic cursor from the earlier Campus Lost & Found project (public/js/cursor.js).
const MAGNETIC = '.btn, .nav > a, .brand, .menu-trigger, [data-magnetic]';
const TEXT_INPUT = 'input:not([type="radio"]):not([type="checkbox"]):not([type="submit"]):not([type="button"]), textarea, select, [contenteditable="true"]';
const RING = 34; // resting ring diameter in px
const PULL = 0.28; // how far a magnetic element leans toward the pointer (share of the offset)
const MAX_LEAN = 8; // px

interface Lean { x: number; y: number; cx: number; cy: number }

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function clamp(value: number, limit: number): number {
  return Math.max(-limit, Math.min(limit, value));
}

/**
 * A small dot tracks the pointer exactly; a ring follows it with spring lag and stretches along the
 * direction of travel. Over buttons and navigation links the ring wraps the element and the element
 * leans toward the pointer. Mouse and trackpad only, off for reduced motion, the system cursor stays
 * visible, and the loop stops whenever everything has come to rest.
 */
@Component({
  selector: 'app-cursor-follower',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="cursor-blob is-hidden" aria-hidden="true" #blob></div>
    <div class="cursor-dot is-hidden" aria-hidden="true" #dot></div>
  `,
})
export class CursorFollower implements OnInit, OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly zone = inject(NgZone);
  private readonly blobRef = viewChild.required<ElementRef<HTMLElement>>('blob');
  private readonly dotRef = viewChild.required<ElementRef<HTMLElement>>('dot');
  private mouse = { x: -100, y: -100 };
  private ring = { x: -100, y: -100, w: RING, h: RING, r: RING / 2 };
  private magnet: HTMLElement | null = null; // element the ring is wrapped around
  private readonly leaning = new Map<HTMLElement, Lean>();
  private pressed = false;
  private frame = 0;
  private enabled = false;
  private reduceMotion: MediaQueryList | null = null;
  private readonly listeners: [EventTarget, string, EventListener][] = [];

  ngOnInit(): void {
    const view = this.document.defaultView;
    // Purely decorative: if the browser cannot tell us about the pointer or motion settings, skip it.
    if (!view || typeof view.matchMedia !== 'function') return;
    const fine = view.matchMedia('(hover: hover) and (pointer: fine)').matches;
    this.reduceMotion = view.matchMedia('(prefers-reduced-motion: reduce)');
    if (!fine || this.reduceMotion.matches) return;
    this.enabled = true;
    const root = this.document.documentElement;
    this.zone.runOutsideAngular(() => {
      this.listen(this.document, 'pointermove', (e) => this.onMove(e as PointerEvent));
      this.listen(this.document, 'pointerover', (e) => this.onOver(e as PointerEvent));
      this.listen(this.document, 'pointerdown', () => { this.pressed = true; this.kick(); });
      this.listen(this.document, 'pointerup', () => { this.pressed = false; this.kick(); });
      // Smooth scrolling moves a wrapped element out from under a still pointer, so follow it.
      this.listen(view, 'scroll', () => this.kick());
      this.listen(root, 'mouseleave', () => {
        this.setHidden(true);
        this.setMagnet(null);
        this.kick();
      });
      // If the visitor turns on reduced motion mid-visit, remove the effect entirely.
      this.listen(this.reduceMotion!, 'change', () => {
        if (this.reduceMotion!.matches) this.disable();
      });
    });
  }

  ngOnDestroy(): void {
    this.disable();
  }

  private disable(): void {
    this.enabled = false;
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    for (const [target, type, fn] of this.listeners) target.removeEventListener(type, fn);
    this.listeners.length = 0;
    this.leaning.forEach((_, el) => (el.style.translate = ''));
    this.leaning.clear();
    this.setHidden(true);
  }

  private listen(target: EventTarget, type: string, fn: EventListener): void {
    target.addEventListener(type, fn, { passive: true });
    this.listeners.push([target, type, fn]);
  }

  private get blob(): HTMLElement {
    return this.blobRef().nativeElement;
  }

  private get dot(): HTMLElement {
    return this.dotRef().nativeElement;
  }

  private setHidden(hidden: boolean): void {
    this.blob.classList.toggle('is-hidden', hidden);
    this.dot.classList.toggle('is-hidden', hidden);
  }

  private setMagnet(el: HTMLElement | null): void {
    this.magnet = el;
    this.blob.classList.toggle('is-magnet', !!el);
    if (el && !this.leaning.has(el)) this.leaning.set(el, { x: 0, y: 0, cx: 0, cy: 0 });
  }

  private onMove(event: PointerEvent): void {
    if (event.pointerType !== 'mouse') return;
    const target = event.target as Element | null;
    if (this.blob.classList.contains('is-hidden') && !target?.closest?.(TEXT_INPUT)) {
      // First move after entering: start the ring where the pointer is, not where it was.
      this.ring.x = event.clientX;
      this.ring.y = event.clientY;
      this.setHidden(false);
    }
    this.mouse = { x: event.clientX, y: event.clientY };
    this.kick();
  }

  private onOver(event: PointerEvent): void {
    if (event.pointerType !== 'mouse') return;
    const target = event.target as Element | null;
    this.setHidden(!!target?.closest?.(TEXT_INPUT));
    // Navy on the page, light over the dark hero.
    const dark = !!target?.closest?.('.beams');
    this.blob.classList.toggle('on-dark', dark);
    this.dot.classList.toggle('on-dark', dark);
    let el = (target?.closest?.(MAGNETIC) ?? null) as HTMLElement | null;
    // Menu items get their own highlight, and disabled controls do not invite a click.
    if (el && (el.closest('[role="menu"]') || (el as HTMLButtonElement).disabled || el.getAttribute('aria-disabled') === 'true')) el = null;
    this.setMagnet(el);
    this.kick();
  }

  private kick(): void {
    if (this.enabled && !this.frame) this.frame = requestAnimationFrame(this.step);
  }

  private readonly step = () => {
    this.frame = 0;
    const view = this.document.defaultView!;
    const ring = this.ring;
    const mouse = this.mouse;
    let target = { x: mouse.x, y: mouse.y, w: RING, h: RING, r: RING / 2 };
    const magnet = this.magnet?.isConnected ? this.magnet : null;
    if (!magnet && this.magnet) this.setMagnet(null);

    if (magnet) {
      const rect = magnet.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      // The ring hugs the element but still drifts a little with the pointer.
      target = {
        x: cx + clamp((mouse.x - cx) * 0.12, 6),
        y: cy + clamp((mouse.y - cy) * 0.12, 6),
        w: rect.width + 10,
        h: rect.height + 10,
        r: (parseFloat(view.getComputedStyle(magnet).borderTopLeftRadius) || 6) + 4,
      };
      const lean = this.leaning.get(magnet)!;
      lean.x = clamp((mouse.x - cx) * PULL, MAX_LEAN);
      lean.y = clamp((mouse.y - cy) * PULL, MAX_LEAN);
    }

    // Spring toward the target: this lag is what makes the ring feel fluid.
    const prevX = ring.x;
    const prevY = ring.y;
    ring.x = lerp(ring.x, target.x, magnet ? 0.22 : 0.18);
    ring.y = lerp(ring.y, target.y, magnet ? 0.22 : 0.18);
    ring.w = lerp(ring.w, target.w, 0.2);
    ring.h = lerp(ring.h, target.h, 0.2);
    ring.r = lerp(ring.r, target.r, 0.2);
    const vx = ring.x - prevX;
    const vy = ring.y - prevY;

    const speed = Math.min(Math.hypot(vx, vy), 40);
    const angle = Math.atan2(vy, vx) * (180 / Math.PI);
    // Stretch along the direction of travel only while free; a wrapped ring stays square to the element.
    const stretch = magnet ? 0 : speed / 40;
    const press = this.pressed ? 0.85 : 1;
    const sx = (1 + stretch * 0.45) * press;
    const sy = (1 - stretch * 0.25) * press;

    const blob = this.blob;
    blob.style.width = `${ring.w.toFixed(1)}px`;
    blob.style.height = `${ring.h.toFixed(1)}px`;
    blob.style.borderRadius = `${ring.r.toFixed(1)}px`;
    blob.style.transform =
      `translate(${(ring.x - ring.w / 2).toFixed(1)}px, ${(ring.y - ring.h / 2).toFixed(1)}px)` +
      (magnet ? '' : ` rotate(${angle.toFixed(1)}deg)`) +
      ` scale(${sx.toFixed(3)}, ${sy.toFixed(3)})`;
    this.dot.style.transform = `translate(${mouse.x - 3}px, ${mouse.y - 3}px)`;

    let moving = Math.abs(ring.x - target.x) > 0.1 || Math.abs(ring.y - target.y) > 0.1
      || Math.abs(ring.w - target.w) > 0.1 || Math.abs(ring.h - target.h) > 0.1;
    // Ease leaning elements toward their lean, or back to rest after the pointer leaves.
    this.leaning.forEach((lean, el) => {
      const active = el === magnet;
      lean.cx = lerp(lean.cx, active ? lean.x : 0, 0.2);
      lean.cy = lerp(lean.cy, active ? lean.y : 0, 0.2);
      if (!active && Math.abs(lean.cx) < 0.05 && Math.abs(lean.cy) < 0.05) {
        el.style.translate = '';
        this.leaning.delete(el);
        return;
      }
      el.style.translate = `${lean.cx.toFixed(2)}px ${lean.cy.toFixed(2)}px`;
      if (Math.abs(lean.cx - (active ? lean.x : 0)) > 0.05 || Math.abs(lean.cy - (active ? lean.y : 0)) > 0.05) moving = true;
    });

    if (moving) this.frame = requestAnimationFrame(this.step);
  };
}
