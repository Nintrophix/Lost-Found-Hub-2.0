# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Students, faculty and staff of SRM Institute of Science and Technology, Ramapuram campus, who have lost something on campus or found something that is not theirs. They sign in with an `@srmist.edu.in` email; no other domain can use the service.
- Staff of the campus lost and found office, who review ownership claims, hold found items and hand them over at the desk after checking the claimant's SRM ID card.
- Administrators, who manage accounts, roles, categories and campus places, and read statistics and the activity log.

Typical moment: a student realises between classes that their phone, ID card or bottle is gone, checks the site on their phone, files a report or claims a found item, and later collects it at the office.

## Product Purpose

Get lost belongings back to their owners on campus with as little friction as possible, without letting anyone walk away with something that is not theirs. Success is an item returned to its verified owner through a recorded handover.

## Positioning

A campus-only service: every account is a verified `@srmist.edu.in` address, reports are compared automatically and the likely matches are explained, ownership is proven privately to staff (never to the finder or the public), and the physical handover is confirmed with a single-use QR code plus an in-person SRM ID check.

## Operating Context

- Lost items are reported with category, place, date and time, colour, brand, description and optional photos. Finders report found items the same way and are asked to leave out the details only the owner would know.
- Matching suggests likely pairs; the person who lost the item confirms or dismisses suggestions. A score never approves a claim.
- Claims go to the lost and found office, which approves or rejects them, marks the item ready for collection, scans the claimant's QR code at the desk and completes the handover after checking the SRM ID card.
- Used on phones between classes as much as on desktop; staff use the staff desk at the office counter.

## Capabilities and Constraints

- Stack is fixed: Angular frontend (plain CSS, Angular CDK allowed), FastAPI backend, SQLite with SQLAlchemy and Alembic. No React or Tailwind; 21st.dev components are ported to Angular.
- Item data is visible only when signed in. Public pages: home (with aggregate counts only), log in, register, privacy policy.
- Accounts store name, email, SRM ID (register number or employee ID), department and optional phone.
- Campus places: the current list is a generic seed. The real Ramapuram building names are not yet recorded and must be confirmed by the owner or set by an admin; do not invent them.
- Open decision: production email sending (SMTP account) is not configured yet.

## Brand Commitments

- Name: Campus Lost & Found Hub.
- A student project for SRMIST Ramapuram. It may say it is for SRM students, but must not use the official SRM logo or present itself as run by the university.
- Owner's binding rules: no purple gradients, no pill-shaped buttons, no emoji icons, no fake reviews, metrics or counters, no vague hero text, no em dashes in copy, no "Vite" or "React" mentions, no placeholder content, no AI-generated stock photos, no "made by AI" tags.
- Owner-confirmed look so far: navy primary, brown-orange for lost, green for found, a dark animated beams background on the home hero, a cursor ring, and advanced but purposeful animation with smooth scrolling.

## Evidence on Hand

- Real counts from the database (open lost reports, found items waiting, items returned) for the home page.
- No testimonials, partner logos, press, usage numbers or photography exist. Do not fabricate any.

## Product Principles

1. Trust before speed: never let a shortcut weaken proof of ownership or the private handling of evidence.
2. Campus-only and honest: show real data or nothing; never invent activity.
3. Built for the moment of loss: the next step is always obvious, on a phone, in one hand.
4. Staff time is precious: queues and handovers are scannable and hard to get wrong.

## Accessibility & Inclusion

- Keyboard and screen-reader support for all flows, including menus and the alert stack.
- All motion respects `prefers-reduced-motion`; decorative effects never carry information.
- Colour is never the only signal for lost, found or status.
