import { Routes } from '@angular/router';

import { roleGuard, signedInGuard } from './core/auth';
import { PageMeta } from './core/seo';

const meta = (data: PageMeta) => data;

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/home').then((m) => m.HomePage),
    data: meta({
      description:
        'Report something you lost or found on campus, see likely matches, and collect your item through a staff-verified handover.',
    }),
  },
  {
    path: 'items',
    canActivate: [signedInGuard],
    loadComponent: () => import('./pages/browse').then((m) => m.BrowsePage),
    // Sign-in pages: crawlers would only reach the login redirect, so they are not indexed.
    data: meta({ title: 'Browse lost and found items', description: 'Search lost and found reports by keyword, category, place and date.', noindex: true }),
  },
  {
    path: 'items/:id',
    canActivate: [signedInGuard],
    loadComponent: () => import('./pages/item-detail').then((m) => m.ItemDetailPage),
    data: meta({ title: 'Item', noindex: true }),
  },
  {
    path: 'report',
    canActivate: [signedInGuard],
    loadComponent: () => import('./pages/report').then((m) => m.ReportPage),
    data: meta({ title: 'Report an item', description: 'Report something you lost or found on campus.', noindex: true }),
  },
  {
    path: 'dashboard',
    canActivate: [signedInGuard],
    loadComponent: () => import('./pages/dashboard').then((m) => m.DashboardPage),
    data: meta({ title: 'My dashboard', noindex: true }),
  },
  {
    path: 'staff',
    canActivate: [roleGuard(['STAFF', 'ADMIN'])],
    loadComponent: () => import('./pages/staff').then((m) => m.StaffPage),
    data: meta({ title: 'Staff desk', noindex: true }),
  },
  {
    path: 'admin',
    canActivate: [roleGuard(['ADMIN'])],
    loadComponent: () => import('./pages/admin').then((m) => m.AdminPage),
    data: meta({ title: 'Administration', noindex: true }),
  },
  {
    path: 'login',
    loadComponent: () => import('./pages/auth-pages').then((m) => m.LoginPage),
    data: meta({ title: 'Log in', description: 'Log in with your campus email address.' }),
  },
  {
    path: 'register',
    loadComponent: () => import('./pages/auth-pages').then((m) => m.RegisterPage),
    data: meta({ title: 'Create an account', description: 'Create an account with your campus email address.' }),
  },
  {
    path: 'verify-email',
    loadComponent: () => import('./pages/auth-pages').then((m) => m.VerifyEmailPage),
    data: meta({ title: 'Confirm your email', noindex: true }),
  },
  {
    path: 'forgot-password',
    loadComponent: () => import('./pages/auth-pages').then((m) => m.ForgotPasswordPage),
    data: meta({ title: 'Forgot password', noindex: true }),
  },
  {
    path: 'reset-password',
    loadComponent: () => import('./pages/auth-pages').then((m) => m.ResetPasswordPage),
    data: meta({ title: 'Choose a new password', noindex: true }),
  },
  {
    path: 'privacy',
    loadComponent: () => import('./pages/privacy').then((m) => m.PrivacyPage),
    data: meta({ title: 'Privacy policy', description: 'What Campus Lost & Found Hub stores, who can see it, and how long it is kept.' }),
  },
  {
    path: '**',
    loadComponent: () => import('./pages/not-found').then((m) => m.NotFoundPage),
    data: meta({ title: 'Page not found', noindex: true }),
  },
];
