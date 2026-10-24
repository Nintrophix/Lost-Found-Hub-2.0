import { DOCUMENT } from '@angular/common';
import { AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, NgZone, OnDestroy, inject, viewChild } from '@angular/core';

/**
 * Faint page-wide background recreating the 21st.dev "Sliding Ease" (uilayout): fine vertical
 * hairlines whose short dashes slide along them with an ease-in-out, each column a little behind
 * its neighbour, so the dashes travel as waves; a slowly drifting field decides where dashes show,
 * forming soft moving blobs. Drawn on one fixed canvas behind all content.
 * Budget: about 30 frames a second, device pixel ratio capped at 1.5, paused in hidden tabs,
 * a single still frame for reduced motion.
 */
const SPACING = 24; // px between hairlines
const DASH = 14; // dash length
const PITCH = 24; // dash length + gap
const CYCLE_MS = 2600; // one eased slide of one pitch
const COLUMN_LAG = 0.035; // share of a cycle each column trails its left neighbour
const FRAME_MS = 1000 / 30;
const INK = '30, 58, 110'; // --primary as rgb

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

@Component({
  selector: 'app-sliding-ease',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<canvas #canvas class="sliding-ease" aria-hidden="true"></canvas>`,
})
export class SlidingEaseBackground implements AfterViewInit, OnDestroy {
  private readonly canvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private readonly document = inject(DOCUMENT);
  private readonly zone = inject(NgZone);
  private ctx: CanvasRenderingContext2D | null = null;
  private width = 0;
  private height = 0;
  private frame = 0;
  private last = 0;
  private reduced = false;
  private readonly onResize = () => this.resize();
  private readonly onVisibility = () => this.run();

  ngAfterViewInit(): void {
    const view = this.document.defaultView;
    if (!view) return;
    this.ctx = this.canvasRef().nativeElement.getContext('2d');
    if (!this.ctx) return;
    this.reduced = typeof view.matchMedia === 'function' && view.matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.zone.runOutsideAngular(() => {
      view.addEventListener('resize', this.onResize, { passive: true });
      this.document.addEventListener('visibilitychange', this.onVisibility);
      this.resize();
    });
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.frame);
    this.document.defaultView?.removeEventListener('resize', this.onResize);
    this.document.removeEventListener('visibilitychange', this.onVisibility);
  }

  private resize(): void {
    const view = this.document.defaultView!;
    const canvas = this.canvasRef().nativeElement;
    const dpr = Math.min(view.devicePixelRatio || 1, 1.5);
    this.width = view.innerWidth;
    this.height = view.innerHeight;
    canvas.width = Math.round(this.width * dpr);
    canvas.height = Math.round(this.height * dpr);
    this.ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.draw(performance.now());
    this.run();
  }

  private run(): void {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    if (!this.reduced && this.document.visibilityState === 'visible') this.frame = requestAnimationFrame(this.tick);
  }

  private readonly tick = (now: number) => {
    if (now - this.last >= FRAME_MS) {
      this.last = now;
      this.draw(now);
    }
    this.frame = requestAnimationFrame(this.tick);
  };

  /** Where dashes appear: a smooth field of drifting blobs, 0 (none) to 1 (strongest). */
  private field(x: number, y: number, t: number): number {
    const a = Math.sin(x * 0.011 + t * 0.00022) * Math.cos(y * 0.009 - t * 0.00017);
    const b = Math.sin((x - y) * 0.006 + t * 0.00011);
    return Math.min(1, Math.max(0, (a * 0.65 + b * 0.35 - 0.12) / 0.6));
  }

  private draw(now: number): void {
    const ctx = this.ctx!;
    ctx.clearRect(0, 0, this.width, this.height);
    const columns = Math.ceil(this.width / SPACING) + 1;
    ctx.fillStyle = `rgba(${INK}, 0.05)`;
    for (let c = 0; c < columns; c++) ctx.fillRect(c * SPACING, 0, 1, this.height);

    for (let c = 0; c < columns; c++) {
      const x = c * SPACING;
      const phase = (((now / CYCLE_MS) - c * COLUMN_LAG) % 1 + 1) % 1;
      const offset = easeInOutCubic(phase) * PITCH;
      for (let y = -PITCH + offset; y < this.height; y += PITCH) {
        const strength = this.field(x, y, now);
        if (strength <= 0.02) continue;
        ctx.fillStyle = `rgba(${INK}, ${(0.05 + strength * 0.11).toFixed(3)})`;
        const w = 1 + strength * 2;
        ctx.fillRect(x + 0.5 - w / 2, y, w, DASH);
      }
    }
  }
}
