import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Item } from '../core/api';
import { Icon, categoryIcon } from './icon';
import { StatusTag } from './status-tag';

@Component({
  selector: 'app-item-card',
  imports: [RouterLink, DatePipe, Icon, StatusTag],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @let it = item();
    <a class="card" [class.lost]="it.report_type === 'LOST'" [class.found]="it.report_type === 'FOUND'"
       [routerLink]="['/items', it.id]">
      <div class="card-media">
        @if (it.images.length) {
          <img [src]="it.images[0].url" [alt]="'Photo of ' + it.title" loading="lazy" />
        } @else {
          <span class="icon-disc"><app-icon [name]="icon()" [size]="52" [strokeWidth]="1.6" /></span>
        }
      </div>
      <div class="card-body">
        <app-status-tag [item]="it" />
        <h3>{{ it.title }}</h3>
        <p class="meta"><app-icon name="pin" [size]="14" />{{ it.location.name }}</p>
        <p class="meta"><app-icon name="calendar" [size]="14" />{{ it.occurred_at | date: 'mediumDate' }}</p>
      </div>
    </a>
  `,
  styles: `:host { display: flex; } :host > a { flex: 1; } p.meta { margin: 0 0 2px; }`,
})
export class ItemCard {
  readonly item = input.required<Item>();
  protected readonly icon = computed(() => categoryIcon(this.item().category.name));
}
