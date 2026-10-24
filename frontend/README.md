# Campus Lost & Found Hub: frontend

Angular 21 single-page app for the FastAPI backend in `../backend`. It uses one global stylesheet (`src/styles.css`), no UI framework, and Angular CDK for the accessible dropdown menu.

## Run locally

Start the backend first (see the root README), then in this folder:

```bash
npm install
```

```bash
npm start
```

Open http://localhost:4200. The dev server proxies `/api` to http://localhost:8000 (`proxy.conf.json`), so cookies and the CSRF header work on the same origin.

## Build

`npm run build` writes the production build to `dist/lost-found-hub/browser` with no source maps. Before it runs, `scripts/generate-sitemap.mjs` writes `public/sitemap.xml` and `public/robots.txt` for `SITE_URL`:

```bash
SITE_URL=https://lostfound.university.edu npm run build
```

## Test

```bash
npm test -- --watch=false
```

## Structure

- `src/app/core`: typed API client (`api.ts`), auth state and route guards (`auth.ts`), page titles, meta, canonical links and JSON-LD (`seo.ts`).
- `src/app/shared`: icons, item card, status tag, breadcrumbs, plus:
  - `alert-stack.ts`: the dismissible alert stack (bottom right). Pages call `Alerts.success()` / `.error()` from `core/alerts.ts`. Timed alerts pause on hover and focus; errors stay until dismissed. `core/notification-feed.ts` shows new unread notifications there (checks every minute while signed in, skips hidden tabs).
  - `account-menu.ts`: header dropdown. Angular port of the 21st.dev / shadcn dropdown menu, built on `@angular/cdk/menu` for menu roles, arrow keys, Escape and focus return.
  - `beams-background.ts`: Angular port of the 21st.dev "Beams Background" (canvas) used behind the home hero. Cyan to blue only, pauses off screen or in hidden tabs, still frame for reduced motion.
  - `cursor-follower.ts`: decorative ring that trails the pointer. Mouse and trackpad only, off for reduced motion; the native cursor stays visible.
- `src/app/pages`: one file per screen. The account pages share `auth-pages.ts`.

21st.dev and shadcn components are written for React and Tailwind. They are adapted into Angular components and this stylesheet, never installed as React code, so the project keeps one framework.

The node engine requirement of Angular 22 (24.15+) is newer than the machine this was built on (24.14), so the project uses Angular 21.
