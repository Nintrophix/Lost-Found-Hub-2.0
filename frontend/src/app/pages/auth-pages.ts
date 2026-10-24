import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { Api, errorMessage } from '../core/api';
import { Auth } from '../core/auth';
import { Breadcrumbs } from '../shared/breadcrumbs';

/** Email links carry their token in the URL fragment (#token=...) so it never reaches server logs. */
function tokenFromFragment(route: ActivatedRoute): string {
  return new URLSearchParams(route.snapshot.fragment ?? '').get('token') ?? '';
}

@Component({
  selector: 'app-login',
  imports: [FormsModule, RouterLink, Breadcrumbs],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page">
      <app-breadcrumbs [crumbs]="[{ label: 'Home', link: '/' }, { label: 'Log in' }]" />
      <div class="form-card">
        <h1>Log in</h1>
        @if (error()) { <div class="alert alert-error" role="alert">{{ error() }}</div> }
        <form (ngSubmit)="submit()">
          <div class="field">
            <label for="email">SRM email <span class="hint">({{ auth.domainHint() }})</span></label>
            <input id="email" name="email" type="email" autocomplete="email" required [(ngModel)]="email"
                   [placeholder]="'yourname' + auth.domainHint()" />
          </div>
          <div class="field">
            <label for="password">Password</label>
            <input id="password" name="password" type="password" autocomplete="current-password" required [(ngModel)]="password" />
          </div>
          <button class="btn" type="submit" [disabled]="busy()">Log in</button>
        </form>
        <p class="small" style="margin-top: 16px">
          <a routerLink="/forgot-password">Forgot your password?</a> ·
          New here? <a routerLink="/register">Create an account</a>
        </p>
      </div>
    </div>
  `,
})
export class LoginPage {
  readonly returnUrl = input<string>();
  protected readonly auth = inject(Auth);
  private readonly router = inject(Router);
  protected readonly error = signal('');
  protected readonly busy = signal(false);
  protected email = '';
  protected password = '';

  protected submit(): void {
    if (!this.auth.emailAllowed(this.email)) {
      this.error.set(`Only ${this.auth.domainHint()} email addresses can use this service.`);
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.auth.login(this.email, this.password).subscribe({
      next: () => {
        const target = this.returnUrl();
        // Only follow same-site paths, never an absolute URL from the query string.
        this.router.navigateByUrl(target && target.startsWith('/') && !target.startsWith('//') ? target : '/dashboard');
      },
      error: (e) => { this.error.set(errorMessage(e)); this.busy.set(false); },
    });
  }
}

@Component({
  selector: 'app-register',
  imports: [FormsModule, RouterLink, Breadcrumbs],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page">
      <app-breadcrumbs [crumbs]="[{ label: 'Home', link: '/' }, { label: 'Create an account' }]" />
      <div class="form-card">
        <h1>Create an account</h1>
        @if (done()) {
          <div class="alert alert-ok" role="status">{{ done() }}</div>
          <p>Open the link in the email to confirm your address, then <a routerLink="/login">log in</a>.</p>
        } @else {
          <p class="muted">Only {{ auth.domainHint() }} addresses can register. We send a link to confirm the address is yours.</p>
          @if (error()) { <div class="alert alert-error" role="alert">{{ error() }}</div> }
          <form (ngSubmit)="submit()">
            <div class="field">
              <label for="name">Full name</label>
              <input id="name" name="name" autocomplete="name" required [(ngModel)]="name" />
            </div>
            <div class="field">
              <label for="email">SRM email</label>
              <input id="email" name="email" type="email" autocomplete="email" required [(ngModel)]="email"
                     [placeholder]="'yourname' + auth.domainHint()" />
            </div>
            <div class="field">
              <label for="campus-id">SRM ID <span class="hint">(register number, or employee ID for staff)</span></label>
              <input id="campus-id" name="campusId" required minlength="5" maxlength="20" autocapitalize="characters"
                     [(ngModel)]="campusId" placeholder="For example: RA2111003010123" />
            </div>
            <div class="field">
              <label for="department">Department</label>
              <input id="department" name="department" required minlength="2" maxlength="100" autocomplete="organization-title"
                     [(ngModel)]="department" placeholder="For example: Computer Science and Engineering" />
            </div>
            <div class="field">
              <label for="phone">Phone <span class="hint">(optional, shown only to you and administrators)</span></label>
              <input id="phone" name="phone" type="tel" autocomplete="tel" maxlength="20" [(ngModel)]="phone" />
            </div>
            <div class="field">
              <label for="password">Password <span class="hint">(at least 8 characters)</span></label>
              <input id="password" name="password" type="password" autocomplete="new-password" minlength="8" required [(ngModel)]="password" />
            </div>
            <button class="btn" type="submit" [disabled]="busy()">Create account</button>
          </form>
          <p class="small" style="margin-top: 16px">Already registered? <a routerLink="/login">Log in</a></p>
        }
      </div>
    </div>
  `,
})
export class RegisterPage {
  private readonly api = inject(Api);
  protected readonly auth = inject(Auth);
  protected readonly error = signal('');
  protected readonly done = signal('');
  protected readonly busy = signal(false);
  protected name = '';
  protected email = '';
  protected password = '';
  protected campusId = '';
  protected department = '';
  protected phone = '';

  protected submit(): void {
    if (!this.auth.emailAllowed(this.email)) {
      this.error.set(`Only ${this.auth.domainHint()} email addresses can register.`);
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.api.register({
      name: this.name,
      email: this.email,
      password: this.password,
      campus_id: this.campusId,
      department: this.department,
      phone: this.phone.trim() || null,
    }).subscribe({
      next: (r) => this.done.set(r.message),
      error: (e) => { this.error.set(errorMessage(e)); this.busy.set(false); },
    });
  }
}

@Component({
  selector: 'app-verify-email',
  imports: [FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page form-card">
      <h1>Confirm your email</h1>
      @if (message()) {
        <div class="alert alert-ok" role="status">{{ message() }}</div>
        <a class="btn" routerLink="/login">Log in</a>
      } @else if (error()) {
        <div class="alert alert-error" role="alert">{{ error() }}</div>
        <p>Request a new link:</p>
        @if (resent()) {
          <div class="alert alert-info" role="status">{{ resent() }}</div>
        } @else {
          <form class="search" (ngSubmit)="resend()">
            <label class="sr-only" for="email">SRM email</label>
            <input id="email" name="email" type="email" required [(ngModel)]="email" placeholder="Your SRM email" />
            <button class="btn" type="submit">Send link</button>
          </form>
        }
      } @else {
        <p class="muted">Checking your link...</p>
      }
    </div>
  `,
})
export class VerifyEmailPage {
  private readonly api = inject(Api);
  protected readonly message = signal('');
  protected readonly error = signal('');
  protected readonly resent = signal('');
  protected email = '';

  constructor() {
    const token = tokenFromFragment(inject(ActivatedRoute));
    if (!token) {
      this.error.set('This link is invalid or has expired.');
      return;
    }
    this.api.verifyEmail(token).subscribe({
      next: (r) => this.message.set(r.message),
      error: (e) => this.error.set(errorMessage(e)),
    });
  }

  protected resend(): void {
    this.api.resendVerification(this.email).subscribe({
      next: (r) => this.resent.set(r.message),
      error: (e) => this.error.set(errorMessage(e)),
    });
  }
}

@Component({
  selector: 'app-forgot-password',
  imports: [FormsModule, RouterLink, Breadcrumbs],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page">
      <app-breadcrumbs [crumbs]="[{ label: 'Home', link: '/' }, { label: 'Log in', link: '/login' }, { label: 'Forgot password' }]" />
      <div class="form-card">
        <h1>Forgot your password?</h1>
        @if (done()) {
          <div class="alert alert-ok" role="status">{{ done() }}</div>
        } @else {
          <p class="muted">Enter your SRM email and we will send a link to choose a new password.</p>
          @if (error()) { <div class="alert alert-error" role="alert">{{ error() }}</div> }
          <form (ngSubmit)="submit()">
            <div class="field">
              <label for="email">SRM email</label>
              <input id="email" name="email" type="email" autocomplete="email" required [(ngModel)]="email" />
            </div>
            <button class="btn" type="submit">Send reset link</button>
          </form>
        }
        <p class="small" style="margin-top: 16px"><a routerLink="/login">Back to log in</a></p>
      </div>
    </div>
  `,
})
export class ForgotPasswordPage {
  private readonly api = inject(Api);
  protected readonly done = signal('');
  protected readonly error = signal('');
  protected email = '';

  protected submit(): void {
    this.api.forgotPassword(this.email).subscribe({
      next: (r) => this.done.set(r.message),
      error: (e) => this.error.set(errorMessage(e)),
    });
  }
}

@Component({
  selector: 'app-reset-password',
  imports: [FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page form-card">
      <h1>Choose a new password</h1>
      @if (done()) {
        <div class="alert alert-ok" role="status">{{ done() }}</div>
        <a class="btn" routerLink="/login">Log in</a>
      } @else {
        @if (error()) { <div class="alert alert-error" role="alert">{{ error() }}</div> }
        <form (ngSubmit)="submit()">
          <div class="field">
            <label for="password">New password <span class="hint">(at least 8 characters)</span></label>
            <input id="password" name="password" type="password" autocomplete="new-password" minlength="8" required [(ngModel)]="password" />
          </div>
          <button class="btn" type="submit">Save password</button>
        </form>
        <p class="small muted" style="margin-top: 16px">This signs you out on every device.</p>
      }
    </div>
  `,
})
export class ResetPasswordPage {
  private readonly api = inject(Api);
  private readonly token = tokenFromFragment(inject(ActivatedRoute));
  protected readonly done = signal('');
  protected readonly error = signal(this.token ? '' : 'This link is invalid or has expired.');
  protected password = '';

  protected submit(): void {
    this.api.resetPassword(this.token, this.password).subscribe({
      next: (r) => this.done.set(r.message),
      error: (e) => this.error.set(errorMessage(e)),
    });
  }
}
