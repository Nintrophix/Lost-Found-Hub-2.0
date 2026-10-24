import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { Item } from '../core/api';

const STATUS_LABELS: Record<string, string> = {
  MATCHED: 'Possible match',
  CLAIMED: 'Being returned',
  RETURNED: 'Returned',
  CLOSED: 'Closed',
};

@Component({
  selector: 'app-status-tag',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="row" style="gap: 6px">
      <span class="tag" [class.tag-lost]="item().report_type === 'LOST'" [class.tag-found]="item().report_type === 'FOUND'">
        {{ item().report_type }}
      </span>
      @if (labels[item().status]; as label) {
        <span class="tag tag-status">{{ label }}</span>
      }
    </span>
  `,
})
export class StatusTag {
  readonly item = input.required<Pick<Item, 'report_type' | 'status'>>();
  protected readonly labels = STATUS_LABELS;
}
