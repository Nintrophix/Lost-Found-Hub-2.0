import { DOCUMENT } from '@angular/common';
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  NgZone,
  OnDestroy,
  inject,
  input,
  viewChild,
} from '@angular/core';

/**
 * Angular port of the 21st.dev "Beams Background" (kokonutd): soft blurred light beams drifting
 * diagonally upward on a dark canvas. Differences from the React original:
 * - Fills its host element (the home hero) instead of the whole window.
 * - Hue limited to cyan through blue (190 to 235) so no purple appears.
 * - Fixes the original resize bug (ctx.scale was applied again on every resize).
 * - Pauses when off screen or in a hidden tab; draws a single still frame for reduced motion.
 */
interface Beam {
  x: number;
  y: number;
  width: number;
  length: number;
  angle: number;
  speed: number;
  opacity: number;
  hue: number;
  pulse: number;
  pulseSpeed: number;
}

const BEAM_COUNT = 30;
const HUE_MIN = 190;
const HUE_RANGE = 45;
const INTENSITY = { subtle: 0.7, medium: 0.85, strong: 1 } as const;

@Component({
  selector: 'app-beams-background',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <canvas #canvas class="beams-canvas" aria-hidden="true"></canvas>
    <div class="beams-veil" aria-hidden="true"></div>
    <div class="beams-content"><ng-content /></div>
  `,
  host: { class: 'beams' },
})
export class BeamsBackground implements AfterViewInit, OnDestroy {
  readonly intensity = input<keyof typeof INTENSITY>('medium');
  private readonly canvasRef = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly zone = inject(NgZone);
  private readonly document = inject(DOCUMENT);

  private ctx: CanvasRenderingContext2D | null = null;
  private beams: Beam[] = [];
  private width = 0;
  private height = 0;
  private frame = 0;
  private onScreen = true;
  private reducedMotion = false;
  private resizeObserver?: ResizeObserver;
  private intersectionObserver?: IntersectionObserver;
  private readonly onVisibility = () => this.updateRunning();

  ngAfterViewInit(): void {
    const canvas = this.canvasRef().nativeElement;
    // Decorative only: without canvas or the observers the hero simply keeps its dark background.
    if (typeof ResizeObserver === 'undefined' || typeof IntersectionObserver === 'undefined') return;
    this.ctx = canvas.getContext('2d');
    if (!this.ctx) return;
    this.reducedMotion = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // The animation loop runs outside Angular so 60 frames a second never trigger change detection.
    this.zone.runOutsideAngular(() => {
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(this.host.nativeElement);
      this.intersectionObserver = new IntersectionObserver(([entry]) => {
        this.onScreen = entry.isIntersecting;
        this.updateRunning();
      });
      this.intersectionObserver.observe(this.host.nativeElement);
      this.document.addEventListener('visibilitychange', this.onVisibility);
      this.resize();
    });
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.frame);
    this.resizeObserver?.disconnect();
    this.intersectionObserver?.disconnect();
    this.document.removeEventListener('visibilitychange', this.onVisibility);
  }

  private resize(): void {
    const canvas = this.canvasRef().nativeElement;
    const rect = this.host.nativeElement.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.width = Math.max(1, rect.width);
    this.height = Math.max(1, rect.height);
    canvas.width = Math.round(this.width * dpr);
    canvas.height = Math.round(this.height * dpr);
    // setTransform (not scale) so repeated resizes do not compound the scaling.
    this.ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.beams = Array.from({ length: BEAM_COUNT }, () => this.createBeam());
    if (this.reducedMotion) this.draw();
    else this.updateRunning();
  }

  private createBeam(): Beam {
    return {
      x: Math.random() * this.width * 1.5 - this.width * 0.25,
      y: Math.random() * this.height * 1.5 - this.height * 0.25,
      width: 30 + Math.random() * 60,
      length: this.height * 2.5,
      angle: -35 + Math.random() * 10,
      speed: 0.6 + Math.random() * 1.2,
      opacity: 0.12 + Math.random() * 0.16,
      hue: HUE_MIN + Math.random() * HUE_RANGE,
      pulse: Math.random() * Math.PI * 2,
      pulseSpeed: 0.02 + Math.random() * 0.03,
    };
  }

  private resetBeam(beam: Beam, index: number): void {
    const spacing = this.width / 3;
    beam.y = this.height + 100;
    beam.x = (index % 3) * spacing + spacing / 2 + (Math.random() - 0.5) * spacing * 0.5;
    beam.width = 100 + Math.random() * 100;
    beam.speed = 0.5 + Math.random() * 0.4;
    beam.hue = HUE_MIN + (index * HUE_RANGE) / this.beams.length;
    beam.opacity = 0.2 + Math.random() * 0.1;
  }

  private updateRunning(): void {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    if (!this.reducedMotion && this.onScreen && this.document.visibilityState === 'visible') {
      this.frame = requestAnimationFrame(this.tick);
    }
  }

  private readonly tick = () => {
    this.beams.forEach((beam, index) => {
      beam.y -= beam.speed;
      beam.pulse += beam.pulseSpeed;
      if (beam.y + beam.length < -100) this.resetBeam(beam, index);
    });
    this.draw();
    this.frame = requestAnimationFrame(this.tick);
  };

  private draw(): void {
    const ctx = this.ctx!;
    ctx.clearRect(0, 0, this.width, this.height);
    ctx.filter = 'blur(35px)';
    const strength = INTENSITY[this.intensity()];
    for (const beam of this.beams) {
      ctx.save();
      ctx.translate(beam.x, beam.y);
      ctx.rotate((beam.angle * Math.PI) / 180);
      const alpha = beam.opacity * (0.8 + Math.sin(beam.pulse) * 0.2) * strength;
      const gradient = ctx.createLinearGradient(0, 0, 0, beam.length);
      const color = (a: number) => `hsla(${beam.hue}, 85%, 65%, ${a})`;
      gradient.addColorStop(0, color(0));
      gradient.addColorStop(0.1, color(alpha * 0.5));
      gradient.addColorStop(0.4, color(alpha));
      gradient.addColorStop(0.6, color(alpha));
      gradient.addColorStop(0.9, color(alpha * 0.5));
      gradient.addColorStop(1, color(0));
      ctx.fillStyle = gradient;
      ctx.fillRect(-beam.width / 2, 0, beam.width, beam.length);
      ctx.restore();
    }
  }
}
