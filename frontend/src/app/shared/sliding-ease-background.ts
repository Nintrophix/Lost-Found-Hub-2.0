import { DOCUMENT } from '@angular/common';
import { AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, NgZone, OnDestroy, inject, viewChild } from '@angular/core';

/**
 * Page-wide background ported from the 21st.dev "Sliding Ease" (uilayout, SlidingEaseVerticalBars):
 * vertical hairlines carrying short bars that slide between two noise patterns with an ease-in-out.
 * Interactive exactly as the original: bars and lines within 180px of the mouse thicken, grow and
 * wobble, the mouse's distance from the centre shifts the slide phase, and every click sends a ripple
 * outward (300px over 2.5s) that pushes the bars it passes. The original paints solid grey on beige;
 * here the same geometry is drawn in faint navy so page content stays readable.
 * One fixed canvas behind all content, paused in hidden tabs, a single still frame for reduced motion.
 */
const COLUMN_WIDTH = 15; // px per column, as in the original
const SPEED = 0.005; // phase advance per 60 fps frame (original animationSpeed)
const MOUSE_RADIUS = 180;
const RIPPLE_MS = 2500;
const RIPPLE_REACH = 300;
const RIPPLE_BAND = 60;
const INK = '30, 58, 110'; // --primary as rgb
const LINE_ALPHA = 0.06;
const BAR_ALPHA = 0.13; // multiplied by the original's 0.8..1 bar opacity

interface Bar { y: number; height: number; width: number }
interface Ripple { x: number; y: number; time: number; intensity: number }

function noise(x: number, y: number, t: number): number {
  return (Math.sin(x * 0.02 + t) * Math.cos(y * 0.02 + t) + Math.sin(x * 0.03 - t) * Math.cos(y * 0.01 + t) + 1) / 2;
}

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/** One column's bars: wherever the noise is above one half, a bar sized by its strength. */
function pattern(offset: number, spacing: number, height: number, columns: number): Bar[][] {
  const result: Bar[][] = [];
  for (let c = 0; c < columns; c++) {
    const bars: Bar[] = [];
    let y = 0;
    while (y < height) {
      const n = noise(c * spacing, y, offset);
      if (n > 0.5) {
        const h = 10 + n * 30;
        bars.push({ y: y + h / 2, height: h, width: 2 + n * 3 });
        y += h + 15;
      } else {
        y += 15;
      }
    }
    result.push(bars);
  }
  return result;
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
  private columns = 0;
  private spacing = COLUMN_WIDTH;
  private from: Bar[][] = []; // the two patterns the bars slide between (fixed per size)
  private to: Bar[][] = [];
  private phase = 0;
  private mouse = { x: -10000, y: -10000 };
  private ripples: Ripple[] = [];
  private frame = 0;
  private last = 0;
  private reduced = false;
  private readonly onResize = () => this.resize();
  private readonly onVisibility = () => this.run();
  // The canvas sits behind the content, so pointer input is read from the window (client coordinates
  // equal canvas coordinates for a fixed full-viewport canvas).
  private readonly onMove = (e: MouseEvent) => {
    this.mouse.x = e.clientX;
    this.mouse.y = e.clientY;
  };
  private readonly onDown = (e: MouseEvent) => {
    const now = Date.now();
    this.ripples.push({ x: e.clientX, y: e.clientY, time: now, intensity: 2 });
    this.ripples = this.ripples.filter((r) => now - r.time < RIPPLE_MS);
  };

  ngAfterViewInit(): void {
    const view = this.document.defaultView;
    if (!view) return;
    this.ctx = this.canvasRef().nativeElement.getContext('2d');
    if (!this.ctx) return;
    this.reduced = typeof view.matchMedia === 'function' && view.matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.zone.runOutsideAngular(() => {
      view.addEventListener('resize', this.onResize, { passive: true });
      this.document.addEventListener('visibilitychange', this.onVisibility);
      if (!this.reduced) {
        view.addEventListener('mousemove', this.onMove, { passive: true });
        view.addEventListener('mousedown', this.onDown, { passive: true });
      }
      this.resize();
    });
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.frame);
    const view = this.document.defaultView;
    view?.removeEventListener('resize', this.onResize);
    view?.removeEventListener('mousemove', this.onMove);
    view?.removeEventListener('mousedown', this.onDown);
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
    this.columns = Math.max(1, Math.floor(this.width / COLUMN_WIDTH));
    this.spacing = this.width / this.columns;
    this.from = pattern(0, this.spacing, this.height, this.columns);
    this.to = pattern(5, this.spacing, this.height, this.columns);
    this.draw(Date.now());
    this.run();
  }

  private run(): void {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.last = 0;
    if (!this.reduced && this.document.visibilityState === 'visible') this.frame = requestAnimationFrame(this.tick);
  }

  private readonly tick = (now: number) => {
    // The original advances a fixed step per frame; scale it by elapsed time so the speed matches
    // its 60 fps look on any refresh rate (capped so a stalled tab does not jump).
    const frames = this.last ? Math.min((now - this.last) / (1000 / 60), 4) : 1;
    this.last = now;
    this.phase += SPEED * frames;
    this.draw(Date.now());
    this.frame = requestAnimationFrame(this.tick);
  };

  private mouseInfluence(x: number, y: number): number {
    const dx = x - this.mouse.x;
    const dy = y - this.mouse.y;
    return Math.max(0, 1 - Math.sqrt(dx * dx + dy * dy) / MOUSE_RADIUS);
  }

  private rippleInfluence(x: number, y: number, now: number): number {
    let total = 0;
    for (const r of this.ripples) {
      const age = now - r.time;
      if (age >= RIPPLE_MS) continue;
      const distance = Math.hypot(x - r.x, y - r.y);
      const radius = (age / RIPPLE_MS) * RIPPLE_REACH;
      if (Math.abs(distance - radius) < RIPPLE_BAND) {
        total += (1 - age / RIPPLE_MS) * r.intensity * (1 - Math.abs(distance - radius) / RIPPLE_BAND);
      }
    }
    return Math.min(total, 1.5);
  }

  private draw(now: number): void {
    const ctx = this.ctx!;
    const t = this.phase;
    ctx.clearRect(0, 0, this.width, this.height);

    // Slide phase: rest, ease across, rest, ease back. The mouse's closeness to the centre nudges it.
    const m = (t % (Math.PI * 2)) + this.mouseInfluence(this.width / 2, this.height / 2) * 0.5;
    const PI = Math.PI;
    let s: number;
    if (m < PI * 0.1) s = 0;
    else if (m < PI * 0.9) s = (m - PI * 0.1) / (PI * 0.8);
    else if (m < PI * 1.1) s = 1;
    else if (m < PI * 1.9) s = 1 - (m - PI * 1.1) / (PI * 0.8);
    else s = 0;
    const q = easeInOutCubic(s);

    for (let c = 0; c < this.columns; c++) {
      const x = c * this.spacing + this.spacing / 2;
      ctx.beginPath();
      ctx.strokeStyle = `rgba(${INK}, ${LINE_ALPHA})`;
      ctx.lineWidth = 1 + this.mouseInfluence(x, this.height / 2) * 2;
      ctx.moveTo(x, 0);
      ctx.lineTo(x, this.height);
      ctx.stroke();

      const a = this.from[c] ?? [];
      const b = this.to[c] ?? [];
      const count = Math.max(a.length, b.length);
      for (let i = 0; i < count; i++) {
        let start = a[i];
        let end = b[i];
        if (!start) start = { y: end.y - 100, height: 0, width: 0 };
        if (!end) end = { y: start.y + 100, height: 0, width: 0 };
        const near = this.mouseInfluence(x, start.y);
        const ripple = this.rippleInfluence(x, start.y, now);
        const wave = Math.sin(c * 0.3 + i * 0.5 + t * 2) * 10 * (q * (1 - q) * 4);
        const wobble = near * Math.sin(t * 3 + c * 0.2) * 15;
        const push = ripple * Math.sin(t * 4 + i * 0.3) * 20;
        const y = start.y + (end.y - start.y) * q + wave + wobble + push;
        const h = start.height + (end.height - start.height) * q + near * 5 + ripple * 8;
        const w = start.width + (end.width - start.width) * q + near * 2 + ripple * 3;
        if (h > 0.1 && w > 0.1) {
          const alpha = Math.min(1, 0.8 + near * 0.2 + ripple * 0.3) * BAR_ALPHA;
          ctx.fillStyle = `rgba(${INK}, ${alpha.toFixed(3)})`;
          ctx.fillRect(x - w / 2, y - h / 2, w, h);
        }
      }
    }
  }
}
