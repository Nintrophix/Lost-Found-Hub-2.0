import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

// Simple stroke icons drawn on a 24x24 grid. Decorative: hidden from screen readers.
const PATHS: Record<string, string> = {
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4',
  plus: 'M12 5v14M5 12h14',
  pin: 'M12 21s-6-5.6-6-11a6 6 0 0 1 12 0c0 5.4-6 11-6 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  calendar: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  check: 'M4 12.5 9 17.5 20 6.5',
  alert: 'M12 3 2 20h20zM12 10v4M12 17h.01',
  bell: 'M6 9a6 6 0 0 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9zM10 20a2 2 0 0 0 4 0',
  close: 'M6 6l12 12M18 6 6 18',
  chevron: 'M6 9l6 6 6-6',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c1.5-4 4.5-6 8-6s6.5 2 8 6',
  dashboard: 'M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z',
  list: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
  shield: 'M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6z',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
  lock: 'M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4',
  logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
  // Category icons
  glasses: 'M2 13a4 4 0 1 0 8 0 4 4 0 0 0-8 0zM14 13a4 4 0 1 0 8 0 4 4 0 0 0-8 0zM10 13h4M2 13 4 7M22 13l-2-6',
  card: 'M3 5h18v14H3zM7 10a2 2 0 1 0 4 0 2 2 0 0 0-4 0zM6 16c.5-1.5 1.7-2.5 3-2.5s2.5 1 3 2.5M14 9h4M14 13h4',
  plug: 'M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4',
  key: 'M8 15a5 5 0 1 1 3.5-1.5L20 5M16 9l2 2M18 7l2 2',
  bag: 'M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2',
  shirt: 'M8 3 3 6l2 5 3-1v11h8V10l3 1 2-5-5-3a4 4 0 0 1-8 0z',
  book: 'M4 4h6a3 3 0 0 1 3 3v14a2 2 0 0 0-2-2H4zM20 4h-5a3 3 0 0 0-3 3v14a2 2 0 0 1 2-2h6z',
  bottle: 'M10 2h4v3h-4zM9 5h6l1 3v12a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2V8z M8 12h8',
  ball: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3.5 9.5c5 1 12 1 17 0M3.5 14.5c5-1 12-1 17 0M12 3c-3 4-3 14 0 18M12 3c3 4 3 14 0 18',
  calculator: 'M6 2h12v20H6zM9 5h6v4H9zM9 13h.01M12 13h.01M15 13h.01M9 17h.01M12 17h.01M15 17h.01',
  tag: 'M3 4.5v6.2c0 .5.2 1 .6 1.4l8.3 8.3c.8.8 2 .8 2.8 0l5.5-5.5c.8-.8.8-2 0-2.8l-8.3-8.3C11.5 3.2 11 3 10.5 3H4.5C3.7 3 3 3.7 3 4.5zM7.5 7.5h.01',
};

const CATEGORY_ICONS: Record<string, string> = {
  Electronics: 'plug',
  'ID and Cards': 'card',
  Keys: 'key',
  Bags: 'bag',
  Clothing: 'shirt',
  'Books and Stationery': 'book',
  'Bottles and Containers': 'bottle',
  Accessories: 'glasses',
  'Sports Equipment': 'ball',
};

export function categoryIcon(category: string): string {
  return CATEGORY_ICONS[category] ?? 'tag';
}

@Component({
  selector: 'app-icon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg [attr.width]="size()" [attr.height]="size()" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         [attr.stroke-width]="strokeWidth()" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"
         focusable="false">
      <path [attr.d]="path()" />
    </svg>
  `,
  styles: `:host { display: inline-flex; flex-shrink: 0; }`,
})
export class Icon {
  readonly name = input.required<string>();
  readonly size = input(18);
  readonly strokeWidth = input(2);
  protected readonly path = computed(() => PATHS[this.name()] ?? PATHS['tag']);
}
