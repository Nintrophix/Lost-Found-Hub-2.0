import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App } from './app';
import { User } from './core/api';
import { Alerts } from './core/alerts';
import { Auth } from './core/auth';

function signIn(role: User['role']): void {
  TestBed.inject(Auth).user.set({
    id: 1, name: 'Sam Rivera', email: 'sam@srmist.edu.in', role, email_verified: true,
    account_status: 'ACTIVE', campus_id: 'EMP1001', department: 'Lost and Found Office', phone: null,
    created_at: '2026-10-24T00:00:00Z',
  });
}

async function render() {
  const fixture = TestBed.createComponent(App);
  await fixture.whenStable();
  return { fixture, el: fixture.nativeElement as HTMLElement };
}

async function openAccountMenu(fixture: Awaited<ReturnType<typeof render>>['fixture']): Promise<HTMLElement> {
  (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('.menu-trigger')!.click();
  await fixture.whenStable();
  // CDK renders the menu in an overlay attached to document.body.
  return document.querySelector<HTMLElement>('.menu')!;
}

describe('App shell', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('shows sign-in links to visitors and no account menu', async () => {
    const { el } = await render();
    expect(el.textContent).toContain('Log in');
    expect(el.textContent).toContain('Create account');
    expect(el.querySelector('.menu-trigger')).toBeNull();
  });

  it('opens an account menu with role-specific items', async () => {
    signIn('STAFF');
    const { fixture, el } = await render();
    const trigger = el.querySelector('.menu-trigger')!;
    expect(trigger.textContent).toContain('Sam');
    expect(trigger.textContent).toContain('SR');

    const menu = await openAccountMenu(fixture);
    expect(menu.getAttribute('role')).toBe('menu');
    expect(menu.textContent).toContain('sam@srmist.edu.in');
    expect(menu.textContent).toContain('Staff desk');
    expect(menu.textContent).not.toContain('Administration');
    expect(menu.querySelector('.menu-item-destructive')?.textContent).toContain('Log out');
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
  });

  it('shows administration only to admins', async () => {
    signIn('ADMIN');
    const { fixture } = await render();
    const menu = await openAccountMenu(fixture);
    expect(menu.textContent).toContain('Administration');
  });

  it('links to the privacy policy from every page', async () => {
    const { el } = await render();
    expect(el.querySelector('footer a[href="/privacy"]')).not.toBeNull();
    TestBed.inject(HttpTestingController).verify();
  });

  it('renders and dismisses alerts from the stack', async () => {
    const alerts = TestBed.inject(Alerts);
    alerts.error('Could not complete that', 'Server said no');
    alerts.success('Saved');
    const { fixture, el } = await render();
    const toasts = el.querySelectorAll('.toast');
    expect(toasts.length).toBe(2);
    expect(toasts[0].textContent).toContain('Saved'); // newest first
    expect(toasts[1].getAttribute('role')).toBe('alert'); // errors are announced assertively
    toasts[1].querySelector<HTMLButtonElement>('.toast-close')!.click();
    await fixture.whenStable();
    expect(el.querySelectorAll('.toast').length).toBe(1);
  });
});

describe('Alerts service', () => {
  it('keeps the newest five and gives errors no timeout', () => {
    const alerts = TestBed.inject(Alerts);
    for (let i = 1; i <= 7; i++) alerts.success(`Alert ${i}`);
    expect(alerts.items().map((a) => a.title)).toEqual(['Alert 7', 'Alert 6', 'Alert 5', 'Alert 4', 'Alert 3']);
    alerts.error('Broken');
    expect(alerts.items()[0].timeout).toBeNull();
    expect(alerts.items()[1].timeout).toBe(6000);
  });
});
