import { CdkMenu, CdkMenuGroup, CdkMenuItem, CdkMenuTrigger } from '@angular/cdk/menu';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { Auth } from '../core/auth';
import { Icon } from './icon';

/**
 * Signed-in user's menu in the header. Angular adaptation of the 21st.dev / shadcn dropdown menu:
 * Angular CDK Menu provides the menu roles, arrow-key navigation, Escape to close and focus return
 * (Radix's job in the React original); the look and the spring-in animation live in styles.css.
 */
@Component({
  selector: 'app-account-menu',
  imports: [CdkMenuTrigger, CdkMenu, CdkMenuGroup, CdkMenuItem, RouterLink, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (auth.user(); as user) {
      <button type="button" class="menu-trigger" [cdkMenuTriggerFor]="menu" aria-label="Account menu">
        <span class="avatar" aria-hidden="true">{{ initials() }}</span>
        <span class="menu-trigger-name">{{ firstName() }}</span>
        <app-icon name="chevron" [size]="16" />
      </button>

      <ng-template #menu>
        <div class="menu" cdkMenu>
          <div class="menu-label">
            <app-icon name="user" [size]="16" />
            <span>
              <span class="menu-label-name">{{ user.name }}</span>
              <span class="menu-label-email">{{ user.email }}</span>
            </span>
          </div>
          <div class="menu-separator" role="separator"></div>
          <div cdkMenuGroup>
            <a class="menu-item" cdkMenuItem routerLink="/dashboard"><app-icon name="dashboard" [size]="16" />My dashboard</a>
            <a class="menu-item" cdkMenuItem routerLink="/items" [queryParams]="{ mine: true }"><app-icon name="list" [size]="16" />My reports</a>
            <a class="menu-item" cdkMenuItem routerLink="/report"><app-icon name="plus" [size]="16" />Report an item</a>
          </div>
          @if (auth.isStaff()) {
            <div class="menu-separator" role="separator"></div>
            <div cdkMenuGroup>
              <a class="menu-item" cdkMenuItem routerLink="/staff"><app-icon name="shield" [size]="16" />Staff desk</a>
              @if (auth.isAdmin()) {
                <a class="menu-item" cdkMenuItem routerLink="/admin"><app-icon name="settings" [size]="16" />Administration</a>
              }
            </div>
          }
          <div class="menu-separator" role="separator"></div>
          <a class="menu-item" cdkMenuItem routerLink="/privacy"><app-icon name="lock" [size]="16" />Privacy policy</a>
          <div class="menu-separator" role="separator"></div>
          <button type="button" class="menu-item menu-item-destructive" cdkMenuItem (cdkMenuItemTriggered)="logout()">
            <app-icon name="logout" [size]="16" />Log out
          </button>
        </div>
      </ng-template>
    }
  `,
})
export class AccountMenu {
  protected readonly auth = inject(Auth);
  private readonly router = inject(Router);

  protected readonly firstName = computed(() => this.auth.user()?.name.trim().split(/\s+/)[0] ?? '');
  protected readonly initials = computed(() => {
    const parts = (this.auth.user()?.name ?? '').trim().split(/\s+/).filter(Boolean);
    return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
  });

  protected logout(): void {
    this.auth.logout().subscribe(() => this.router.navigate(['/']));
  }
}
