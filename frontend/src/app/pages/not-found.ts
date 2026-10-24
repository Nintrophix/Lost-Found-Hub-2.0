import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-not-found',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page" style="max-width: 640px">
      <p class="tag tag-status" style="margin-bottom: 12px">Error 404</p>
      <h1>We could not find that page</h1>
      <p>The link may be old, or the report may have been closed. These pages may help:</p>
      <ul>
        <li><a routerLink="/">Home page</a></li>
        <li><a routerLink="/items">Browse lost and found items</a></li>
        <li><a routerLink="/report">Report an item</a></li>
        <li><a routerLink="/dashboard">Your dashboard</a></li>
      </ul>
    </div>
  `,
})
export class NotFoundPage {}
