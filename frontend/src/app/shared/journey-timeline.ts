import { DOCUMENT } from '@angular/common';
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  NgZone,
  OnDestroy,
  inject,
  viewChild,
  viewChildren,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { Icon } from './icon';

const READING_LINE = 0.66; // share of the viewport height

/**
 * "How it works" as a scroll-linked journey. Angular port of the 21st.dev Timeline (Aceternity):
 * sticky step titles and a beam that fills its track as the section scrolls through the viewport.
 * Here the beam runs from the "lost" colour to the "found" colour, so its progress is the story,
 * and each step shows a labelled example of the real interface at that stage instead of stock images.
 * Without JavaScript, or with reduced motion, every step is simply shown and the track is full.
 */
@Component({
  selector: 'app-journey-timeline',
  imports: [RouterLink, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="journey" #root>
      <div class="journey-track" aria-hidden="true"><div class="journey-beam" #beam></div></div>

      <article class="journey-step" #step>
        <div class="journey-marker" aria-hidden="true"><span></span></div>
        <h3 class="journey-title">Report it</h3>
        <div class="journey-body">
          <p>Say what it is, where and when. Photos are re-saved without their hidden location data.</p>
          <div class="vignette" aria-label="Example report form">
            <span class="vignette-label">Example</span>
            <div class="vg-field"><span>What</span><strong>Black Pixel phone, cracked blue case</strong></div>
            <div class="vg-row">
              <div class="vg-field"><span>Where</span><strong>Library, 2nd floor</strong></div>
              <div class="vg-field"><span>When</span><strong>Today, 10:40</strong></div>
            </div>
            <div class="vg-choice"><span class="tag tag-lost">LOST</span><span class="tag tag-status">FOUND</span></div>
          </div>
        </div>
      </article>

      <article class="journey-step" #step>
        <div class="journey-marker" aria-hidden="true"><span></span></div>
        <h3 class="journey-title">See likely matches</h3>
        <div class="journey-body">
          <p>Reports are compared by category, words, colour, place and date, and every suggestion says why. It is only a suggestion: nothing is approved automatically.</p>
          <div class="vignette" aria-label="Example match suggestion">
            <span class="vignette-label">Example</span>
            <div class="vg-match">
              <strong>Black Pixel phone</strong>
              <span class="vg-score">88% similar</span>
            </div>
            <ul class="vg-reasons">
              <li><app-icon name="check" [size]="14" />Both in Electronics</li>
              <li><app-icon name="check" [size]="14" />Shared words: black, pixel, cracked</li>
              <li><app-icon name="check" [size]="14" />Found a day after it was lost</li>
            </ul>
          </div>
        </div>
      </article>

      <article class="journey-step" #step>
        <div class="journey-marker" aria-hidden="true"><span></span></div>
        <h3 class="journey-title">Prove it is yours</h3>
        <div class="journey-body">
          <p>Tell the lost and found office something only the owner would know. The person who found it never sees your answer.</p>
          <div class="vignette" aria-label="Example ownership claim">
            <span class="vignette-label">Example</span>
            <div class="vg-field"><span>Proof of ownership</span><strong>The lock screen is a photo of a beagle, and there is a bus pass inside the case.</strong></div>
            <p class="vg-note"><app-icon name="lock" [size]="14" />Only staff can read this</p>
          </div>
        </div>
      </article>

      <article class="journey-step" #step>
        <div class="journey-marker" aria-hidden="true"><span></span></div>
        <h3 class="journey-title">Collect it</h3>
        <div class="journey-body">
          <p>Once approved, show the one-time QR code from your dashboard at the lost and found office. Staff check your SRM ID card, then hand it over.</p>
          <div class="vignette vg-handover" aria-label="Example handover">
            <span class="vignette-label">Example</span>
            <svg class="vg-qr" viewBox="0 0 21 21" aria-hidden="true">
              <path d="M0 0h7v7H0zM1 1v5h5V1zM2 2h3v3H2zM14 0h7v7h-7zM15 1v5h5V1zM16 2h3v3h-3zM0 14h7v7H0zM1 15v5h5v-5zM2 16h3v3H2zM9 0h2v2H9zM12 2h1v3h-1zM8 4h3v1H8zM9 8h3v2H9zM14 9h2v1h-2zM18 8h3v2h-3zM8 12h2v3H8zM12 12h4v1h-4zM17 12h2v3h-2zM12 15h2v2h-2zM15 17h3v1h-3zM9 18h3v3H9zM19 17h2v4h-2zM14 19h2v2h-2zM0 9h3v1H0zM4 9h2v3H4z"/>
            </svg>
            <div>
              <strong>Works once, for 15 minutes</strong>
              <p class="vg-note"><app-icon name="card" [size]="14" />SRM ID card checked at the desk</p>
            </div>
          </div>
          <a class="btn" routerLink="/report" style="margin-top: 20px">Report an item</a>
        </div>
      </article>
    </div>
  `,
})
export class JourneyTimeline implements AfterViewInit, OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly zone = inject(NgZone);
  private readonly root = viewChild.required<ElementRef<HTMLElement>>('root');
  private readonly beam = viewChild.required<ElementRef<HTMLElement>>('beam');
  private readonly steps = viewChildren<ElementRef<HTMLElement>>('step');
  private frame = 0;
  private readonly onScroll = () => {
    if (!this.frame) this.frame = requestAnimationFrame(this.update);
  };

  ngAfterViewInit(): void {
    const view = this.document.defaultView;
    const reduced = !view || typeof view.matchMedia !== 'function'
      || view.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) return; // CSS shows the full beam and every step as reached.
    this.root().nativeElement.classList.add('is-animated');
    this.zone.runOutsideAngular(() => {
      view!.addEventListener('scroll', this.onScroll, { passive: true });
      view!.addEventListener('resize', this.onScroll, { passive: true });
      this.update();
    });
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.frame);
    this.document.defaultView?.removeEventListener('scroll', this.onScroll);
    this.document.defaultView?.removeEventListener('resize', this.onScroll);
  }

  // The beam's tip follows a reading line two thirds down the viewport, and a step counts as reached
  // once its marker crosses that line. (The original's 10%..50% window kept the tip in the top half
  // of the screen, so the step being read stayed unrevealed until it had scrolled well past.)
  private readonly update = () => {
    this.frame = 0;
    const view = this.document.defaultView!;
    const rect = this.root().nativeElement.getBoundingClientRect();
    const readingLine = view.innerHeight * READING_LINE;
    const progress = Math.min(1, Math.max(0, (readingLine - rect.top) / Math.max(1, rect.height)));
    const beam = this.beam().nativeElement;
    beam.style.transform = `scaleY(${progress})`;
    beam.style.opacity = String(Math.min(1, progress * 10));
    for (const step of this.steps()) {
      const marker = step.nativeElement.querySelector('.journey-marker')!.getBoundingClientRect();
      step.nativeElement.classList.toggle('reached', marker.top + marker.height / 2 <= readingLine);
    }
  };
}
