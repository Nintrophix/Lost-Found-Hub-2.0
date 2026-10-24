import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { Auth } from './core/auth';
import { AccountMenu } from './shared/account-menu';
import { AlertStack } from './shared/alert-stack';
import { CursorFollower } from './shared/cursor-follower';
import { Icon } from './shared/icon';
import { SlidingEaseBackground } from './shared/sliding-ease-background';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon, AccountMenu, AlertStack, CursorFollower, SlidingEaseBackground],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-sliding-ease />
    <header class="site-header">
      <div class="container">
        <a class="brand" routerLink="/">
          <img src="favicon.svg" alt="" width="32" height="32" />
          <span>Campus Lost &amp; Found Hub</span>
        </a>
        <nav class="nav" aria-label="Main">
          <a routerLink="/items" routerLinkActive="active">Browse items</a>
          @if (auth.signedIn()) {
            <app-account-menu />
          } @else {
            <a routerLink="/login" routerLinkActive="active">Log in</a>
            <a class="hide-xs" routerLink="/register" routerLinkActive="active">Create account</a>
          }
          <a class="btn" routerLink="/report"><app-icon name="plus" [size]="16" />Report<span class="hide-sm">an item</span></a>
        </nav>
      </div>
    </header>

    <main id="main">
      <router-outlet />
    </main>

    <footer class="site-footer">
      <div class="container spread">
        <span>Campus Lost &amp; Found Hub</span>
        <nav aria-label="Footer">
          <a routerLink="/">Home</a>
          <a routerLink="/items">Browse items</a>
          <a routerLink="/report">Report an item</a>
          <a routerLink="/privacy">Privacy policy</a>
        </nav>
      </div>
    </footer>

    <app-alert-stack />
    <app-cursor-follower />
  `,
})
export class App {
  protected readonly auth = inject(Auth);
}
