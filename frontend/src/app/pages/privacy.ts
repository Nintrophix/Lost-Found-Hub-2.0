import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Breadcrumbs } from '../shared/breadcrumbs';

@Component({
  selector: 'app-privacy',
  imports: [RouterLink, Breadcrumbs],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="container page" style="max-width: 760px">
      <app-breadcrumbs [crumbs]="[{ label: 'Home', link: '/' }, { label: 'Privacy policy' }]" />
      <h1>Privacy policy</h1>
      <p class="muted">Last updated 24 October 2026</p>

      <h2>What we store</h2>
      <ul>
        <li><strong>Your account:</strong> name, SRM email address (only @srmist.edu.in addresses can register), SRM ID (register number or employee ID), department, phone number if you give one, a securely hashed password (never the password itself), your role and when you confirmed your email.</li>
        <li><strong>Reports:</strong> the title, description, category, place, date, colour and brand you enter, and any photos you upload.</li>
        <li><strong>Photos:</strong> every photo is re-saved on upload, which removes hidden metadata such as GPS location and camera details.</li>
        <li><strong>Claims:</strong> the proof of ownership you write, and the staff decision with any note.</li>
        <li><strong>Handover records:</strong> when a handover was scheduled, scanned and completed. QR codes are stored only in a scrambled form and stop working after one use or 15 minutes.</li>
        <li><strong>Activity log:</strong> a record of actions such as sign-ins, approvals and handovers, used to investigate problems. It never contains passwords, codes or claim evidence.</li>
      </ul>

      <h2>Who can see it</h2>
      <ul>
        <li>Reports are visible only to signed-in members of the campus community. Your name and email are never shown on a report.</li>
        <li>Claim evidence is visible only to you and campus staff. The person who found the item cannot see it.</li>
        <li>Staff see a claimant's name, SRM ID and email so they can check the SRM ID card at handover. Staff do not see phone numbers.</li>
        <li>Administrators can see account details and the activity log to run the service.</li>
      </ul>

      <h2>Cookies</h2>
      <p>
        We use two cookies, both only to keep you signed in safely: a session cookie that scripts cannot read, and a
        security token that protects your account from forged requests. There are no advertising, analytics or
        tracking cookies.
      </p>

      <h2>Emails</h2>
      <p>We email you only to confirm your address, reset your password, or tell you that an account already exists for your address.</p>

      <h2>How long we keep it</h2>
      <ul>
        <li>Signed-out and expired sessions, and used or expired email links, are deleted by regular maintenance.</li>
        <li>Reports, claims and handover records are kept as a record of what was returned to whom. Closing a report hides it from searches.</li>
      </ul>

      <h2>Your choices</h2>
      <p>
        You can update your name, department and phone number on your dashboard, close your own reports, withdraw
        a claim before the handover, and change your password at any time.
        To correct or remove other information, contact your campus lost and found office, who run this service.
      </p>

      <p><a routerLink="/">Back to the home page</a></p>
    </div>
  `,
})
export class PrivacyPage {}
