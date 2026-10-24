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
  - `cursor-follower.ts`: fluid magnetic cursor ported from the earlier Campus Lost & Found project: a dot on the pointer and a spring-lagged ring that stretches as it moves and wraps buttons and header links, which lean toward the pointer. Mouse and trackpad only, off for reduced motion; the native cursor stays visible.
  - `journey-timeline.ts`: the home page's four steps. Port of the 21st.dev Timeline (Aceternity): sticky step titles and a beam, lost colour to found colour, that fills as you scroll; each step shows a labelled example of the real interface.
  - `sliding-ease-background.ts`: faint page-wide background ported from the 21st.dev "Sliding Ease" (same algorithm and interaction: bars react within 180px of the mouse, clicks send ripples). One fixed canvas, paused in hidden tabs, still frame and no interaction for reduced motion.
- `src/app/core/smooth-scroll.ts`: Lenis inertial scrolling for mouse and trackpad (native scrolling on touch and for reduced motion).
- Type: Bricolage Grotesque (headings) and Atkinson Hyperlegible Next (body), self-hosted through `@fontsource-variable` packages; no external font requests.
- Route changes use the View Transitions API: an item card morphs into its detail page (`view-transition-name` on the card media and title).
- `src/app/pages`: one file per screen. The account pages share `auth-pages.ts`.

21st.dev and shadcn components are written for React and Tailwind. They are adapted into Angular components and this stylesheet, never installed as React code, so the project keeps one framework.

The node engine requirement of Angular 22 (24.15+) is newer than the machine this was built on (24.14), so the project uses Angular 21.
