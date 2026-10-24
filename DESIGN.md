---
name: Campus Lost & Found Hub
description: A campus-only lost and found service for SRMIST Ramapuram, from report to verified handover.
colors:
  primary: "#1e3a6e"
  primary-hover: "#172d56"
  lost: "#92400e"
  lost-hover: "#78350f"
  lost-accent: "#d97706"
  lost-tint: "#fef3c7"
  found: "#166534"
  found-hover: "#14532d"
  found-accent: "#16a34a"
  found-tint: "#dcfce7"
  danger: "#b91c1c"
  danger-tint: "#fee2e2"
  ink: "#0f172a"
  text: "#334155"
  muted: "#556173"
  line: "#e2e8f0"
  border-strong: "#cbd5e1"
  surface: "#ffffff"
  soft: "#f1f5f9"
  page: "#f6f5f1"
  hero: "#0a0f1c"
  hero-text: "#c9d3e1"
  focus-ring: "#93c5fd"
typography:
  display:
    fontFamily: "Bricolage Grotesque Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(2.5rem, 6vw, 4.6rem)"
    fontWeight: 780
    lineHeight: 1.02
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Bricolage Grotesque Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(2rem, 4vw, 2.9rem)"
    fontWeight: 760
    lineHeight: 1.12
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Bricolage Grotesque Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "clamp(1.4rem, 2.2vw, 1.75rem)"
    fontWeight: 720
    lineHeight: 1.12
    letterSpacing: "-0.02em"
  title-sm:
    fontFamily: "Bricolage Grotesque Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "1.12rem"
    fontWeight: 680
    lineHeight: 1.12
    letterSpacing: "-0.01em"
  numeral:
    fontFamily: "Bricolage Grotesque Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 700
    lineHeight: 1
    fontFeature: "tnum"
  body:
    fontFamily: "Atkinson Hyperlegible Next Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Atkinson Hyperlegible Next Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 600
    lineHeight: 1.3
  tag:
    fontFamily: "Atkinson Hyperlegible Next Variable, Segoe UI, system-ui, sans-serif"
    fontSize: "0.72rem"
    fontWeight: 700
    letterSpacing: "0.04em"
rounded:
  xs: "4px"
  sm: "6px"
  lg: "10px"
  round: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  base: "16px"
  lg: "24px"
  xl: "32px"
  section: "56px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "9px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.surface}"
  button-lost:
    backgroundColor: "{colors.lost}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "9px 16px"
  button-lost-hover:
    backgroundColor: "{colors.lost-hover}"
  button-found:
    backgroundColor: "{colors.found}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "9px 16px"
  button-found-hover:
    backgroundColor: "{colors.found-hover}"
  button-outline:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "9px 16px"
  button-outline-hover:
    backgroundColor: "{colors.soft}"
  button-danger:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.danger}"
    rounded: "{rounded.sm}"
    padding: "9px 16px"
  button-danger-hover:
    backgroundColor: "{colors.danger-tint}"
  button-sm:
    rounded: "{rounded.sm}"
    padding: "5px 10px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "9px 12px"
  card-item:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "12px 14px 16px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "18px"
  tag-lost:
    backgroundColor: "{colors.lost-tint}"
    textColor: "{colors.lost}"
    typography: "{typography.tag}"
    rounded: "{rounded.xs}"
    padding: "2px 8px"
  tag-found:
    backgroundColor: "{colors.found-tint}"
    textColor: "{colors.found}"
    typography: "{typography.tag}"
    rounded: "{rounded.xs}"
    padding: "2px 8px"
  tag-status:
    backgroundColor: "{colors.soft}"
    textColor: "{colors.text}"
    typography: "{typography.tag}"
    rounded: "{rounded.xs}"
    padding: "2px 8px"
  menu:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "4px"
  menu-item:
    rounded: "{rounded.sm}"
    padding: "8px 10px"
  toast:
    backgroundColor: "{colors.surface}"
    padding: "12px 12px 14px 14px"
---

# Design System: Campus Lost & Found Hub

## Overview

**Creative North Star: "The Lost and Found Desk"**

The system is the campus office counter made into a website: a calm, orderly navy desk where every item is logged, tagged lost or found, and handed back in person. Surfaces are white index cards and panels laid on a warm off-white ground, held together by thin slate hairlines and soft one-pixel shadows. Colour carries meaning before it carries mood: navy is the service itself, brown-orange is something missing, green is something waiting to go home. The one dark room is the home hero, where slow cyan-to-blue light beams drift behind the opening question.

Density is practical rather than airy. Pages are used between classes on a phone and at a staff counter on desktop, so lists, tables and forms stay compact and scannable, with generous space reserved for the hero and the home journey. Motion is advanced but purposeful: things come into focus, lists arrive once, a card opens into its own detail page, and the journey beam fills from lost to found as you scroll. Every motion has a reduced-motion path, and none of it carries information.

The owner has rejected purple gradients, pill-shaped buttons, emoji icons, fabricated metrics or reviews, vague hero text, placeholder content and AI-generated stock photography. These are binding.

**Key Characteristics:**
- Navy primary, brown-orange for lost, green for found; the pair is the brand's story.
- Warm off-white page ground with a faint animated navy hairline pattern behind all content.
- White cards and panels with slate hairline borders and a near-invisible resting shadow.
- Bricolage Grotesque for headings and numerals, Atkinson Hyperlegible Next for everything read.
- Gently squared corners (6px default); nothing is a pill.
- One exponential ease-out drives nearly all motion; every effect has a reduced-motion fallback.

## Colors

A sober navy and slate desk palette, with two semantic hues that always mean the same thing.

### Primary
- **Counter Navy** (primary): the service's own voice. Default buttons, links, the active nav item, the count badge, the avatar, text selection, caret and accent-color, the favicon tile, and the default top border on item cards. Its hover step, **Deep Counter Navy** (primary-hover), darkens on hover only.

### Secondary
- **Lost Umber** (lost): text and fill for anything about a missing item: the "I lost something" button, the LOST tag text, the lost category icon. Hovers to **Dark Umber** (lost-hover).
- **Lost Amber** (lost-accent): the brighter signal for lost on structural marks: lost card top border, lost stat swatch, the start of the journey beam and its first marker.
- **Lost Cream** (lost-tint): background of the LOST tag.

### Tertiary
- **Found Forest** (found): text and fill for found items: the "I found something" button, FOUND tag text, match scores. Hovers to **Deep Forest** (found-hover).
- **Found Leaf** (found-accent): found card top border, found stat swatch, journey beam end and reached markers, success timers and checkmarks.
- **Found Mint** (found-tint): FOUND tag and success alert backgrounds.
- **Alarm Red** (danger) and **Alarm Blush** (danger-tint): destructive buttons, destructive menu items, error alerts. Never used decoratively.

### Neutral
- **Slate Ink** (ink): headings, labels, field text, table values.
- **Slate Text** (text): running body copy.
- **Quiet Slate** (muted): hints, meta lines, table headers, footer; tuned to stay above 4.5:1 on the soft and white surfaces.
- **Hairline** (line): every resting border, divider, table rule and separator.
- **Firm Hairline** (border-strong): input borders, outline-button borders, dashed empty states.
- **Index White** (surface): cards, panels, inputs, menus, toasts, the header.
- **Desk Mist** (soft): hover fills, status tags, the translucent band behind recent items.
- **Warm Paper** (page): the page ground under the Sliding Ease pattern; also the footer (at 85% opacity) and the journey marker halos.
- **Night Room** (hero): the beams hero only. **Hero Mist** (hero-text) is its secondary text.
- **Focus Blue** (focus-ring): the 3px focus outline everywhere, and the inset ring on menu items.

### Named Rules
**The Lost Is Warm, Found Is Green Rule.** Brown-orange means lost and green means found, on every surface, every time. Neither hue is used for decoration or for any other meaning, and colour is never the only signal: the word LOST or FOUND always accompanies it.

**The No Purple Rule.** No purple anywhere, including gradients and the hero beams (which stay in the cyan-to-blue range, hue 190 to 235).

**The Two-Step Semantic Rule.** Each semantic hue has a deep step for text and fills (lost, found) and a bright step for marks, borders and swatches (lost-accent, found-accent). Use the deep step whenever text sits on it or in it.

## Typography

**Display Font:** Bricolage Grotesque Variable (with Segoe UI, system-ui, sans-serif)
**Body Font:** Atkinson Hyperlegible Next Variable (with Segoe UI, system-ui, sans-serif)

**Character:** A characterful, slightly quirky grotesque for headings, set heavy and tight, paired with a body face designed for low-vision legibility. The headline face gives the service a voice; the body face keeps every form, hint and table unmistakable.

### Hierarchy
- **Display** (780, clamp(2.5rem, 6vw, 4.6rem), 1.02, -0.035em): the home hero question only, max 14ch, one line per sentence with the second line in a pale found green.
- **Headline** (760, clamp(2rem, 4vw, 2.9rem), 1.12, -0.03em): page h1.
- **Title** (720, clamp(1.4rem, 2.2vw, 1.75rem), 1.12, -0.02em): section h2. The home journey intro enlarges it to clamp(1.9rem, 3.6vw, 2.8rem).
- **Title Small** (680, 1.12rem, 1.12, -0.01em): h3, card titles, panel headings.
- **Numeral** (700, 1.75rem, tabular): stat values; the hero listing counts run larger at clamp(2rem, 3.5vw, 2.6rem).
- **Body** (400, 1.0625rem, 1.6): running copy, hero lede at 1.15rem and max 58ch; `.small` steps down to 0.875rem.
- **Label** (600, 0.95rem): field labels and button text; hints drop to 400 at 0.85rem in Quiet Slate.
- **Tag** (700, 0.72rem, 0.04em): LOST, FOUND and status tags.

### Named Rules
**The Display Is for Headings Rule.** Bricolage appears only on h1 to h3 and on numerals. Everything a person reads or types is Atkinson Hyperlegible Next. Small headings that act as labels (the hero listings heading) switch to the body face.

**The Tabular Numbers Rule.** Counts, scores, table cells and badges use tabular figures so columns of numbers do not jitter.

## Layout

A single centred column, `min(1180px, 100% - 32px)`, with page padding of 24px above and 56px below. Long-form pages narrow the column (privacy 760px, not-found and the report form 640px, auth forms 460px). The home page alternates full-width bands: the dark hero, a translucent soft band of recent items between hairlines (clamp(40px, 6vw, 72px) vertical padding), then the journey section (clamp(56px, 8vw, 104px)).

Grids are auto-fitting rather than breakpoint-driven: item cards fill at a 230px minimum with 20px gaps, two-column forms at 300px, stats at 180px, filters at 170px. The hero is a 1.5 : 0.85 two-column grid aligned to the bottom; the item detail page is content plus a 280 to 380px side column. Both collapse to one column at 860px. The journey collapses at 720px; the header compacts at 640px (nav drops to its own row, the Report button shortens) and hides "Create account" below 400px.

Spacing rhythm is 4, 8, 12, 16, 24, 32 and 56px, with fluid clamp() values for section-scale gaps. Stacks space children 16px apart; inline rows use 12px.

## Elevation & Depth

Mostly flat with a whisper of lift. Resting surfaces get a one-pixel ambient shadow so white cards read as paper on the warm ground; real lift appears only on hover and on floating layers. The page has two ambient depth layers that never hold content: the fixed Sliding Ease canvas (navy hairlines at 5% with dashes up to 16%) behind everything, and the blurred beams canvas inside the hero.

### Shadow Vocabulary
- **Resting** (`box-shadow: 0 1px 2px rgb(15 23 42 / 0.06)`): cards, panels and stats at rest.
- **Lift** (`box-shadow: 0 14px 30px -12px rgb(15 23 42 / 0.28), 0 2px 6px rgb(15 23 42 / 0.06)`): item card hover, paired with a 4px rise.
- **Button hover** (`box-shadow: 0 6px 16px -8px rgb(15 23 42 / 0.5)`): filled buttons on hover; removed on press.
- **Floating** (`box-shadow: 0 16px 40px rgb(15 23 42 / 0.16)` for menus, `0 18px 40px -16px rgb(15 23 42 / 0.35), 0 2px 6px rgb(15 23 42 / 0.06)` for toasts): layers above the page.
- **Example sheet** (`box-shadow: 0 20px 40px -24px rgb(15 23 42 / 0.3)`): journey vignettes.

### Named Rules
**The Lift on Intent Rule.** Shadows deepen only in answer to a pointer or because the layer floats. Nothing rests at Lift.

**The Soft Shadow Rule.** Every shadow is a blurred, slate-tinted ambient shadow. No hard offset shadows.

## Shapes

Gently squared corners throughout. The default radius is 6px (buttons, inputs, cards, panels, alerts, menu items, gallery images); small inline marks (tags, the count badge, the avatar, the vignette label) use 4px; larger floating or framed surfaces (menu, vignettes, detail media) use 10px. Circles are reserved for the category icon disc, journey markers and the cursor dot; the cursor ring is a 34px circle at rest and takes the shape of the element it wraps. Borders are 1px hairlines; the only heavier border is the 3px coloured top edge of item cards. Swatches before stat and listing labels are 10px squares at 2px radius.

**The No Pill Rule.** Buttons and tags never take a pill or fully rounded shape. Nothing interactive exceeds 10px radius.

## Components

### Buttons
Solid, compact and unmistakable.
- **Shape:** gently squared (6px), 1px border, label weight 600 at 0.95rem, optional 16px leading icon with an 8px gap.
- **Primary:** Counter Navy fill, white text, 9px 16px padding. Hero buttons pad to 11px 20px.
- **Lost / Found:** the same button in Lost Umber or Found Forest, used for the two entry actions.
- **Hover / Focus / Active:** fill darkens one step and gains the button-hover shadow over 0.18s; press drops 1px and scales to 0.985; focus shows the 3px Focus Blue outline at 2px offset; disabled is 55% opacity.
- **Outline:** white with Firm Hairline border and ink text; hover fills Desk Mist.
- **Danger:** white with a red hairline and Alarm Red text; hover fills Alarm Blush.
- **On dark:** pale navy (#e8eef9) with navy text, for the hero search only.
- **Small:** 5px 10px at 0.85rem, for table and list actions.
- **Link button:** underlined primary text with no chrome, for inline actions in alerts and lists.

### Tags
- **Style:** 0.72rem bold with 0.04em tracking, 2px 8px padding, 4px radius, 1px border in a mid tone of its family.
- **Variants:** LOST (Lost Cream on Lost Umber, amber border), FOUND (Found Mint on Found Forest, green border), status (Desk Mist with slate text) for plain-language states such as "Possible match" or "Being returned".

### Cards / Containers
- **Item card:** white, 6px radius, hairline border with a 3px top border in navy, Lost Amber or Found Leaf. A 4:3 media area shows the first photo, or a 96px translucent white disc holding the category stroke icon on a warm (#ece9e4) or cool green (#e7ebe8) ground. Body padding 12px 14px 16px: tag row, Title Small heading, then pin and calendar meta lines in Quiet Slate. Hover rises 4px to Lift over 0.35s, the border firms, the title turns navy, the photo scales to 1.045 and the disc tilts. The media and title carry view-transition names so the card morphs into the detail page.
- **Panel / Stat:** white, hairline border, 6px radius, Resting shadow, 18px (panel) or 16px (stat) padding. Stats pair a swatch-led label with a Numeral value.
- **Empty state:** dashed Firm Hairline border, white, 24px padding, centred muted text, always with a next step.

### Inputs / Fields
- **Style:** white, Firm Hairline border, 6px radius, 9px 12px padding, ink text, navy caret; labels sit above at Label weight with hints inline in Quiet Slate.
- **Focus:** the global 3px Focus Blue outline at 2px offset.
- **Error:** errors surface in an alert block (Alarm Blush ground, red hairline, dark red text) above the form.

### Navigation
- **Header:** white bar with a bottom hairline, 64px minimum height; favicon and name at left, then text links in ink at weight 500 that turn navy and underline on hover, navy when active, and a primary Report button at the end. Signed-in users get the account menu.
- **Account menu:** a CDK menu. The trigger is a hairline-bordered 6px button with a 28px navy initials square and a chevron that flips when open. The panel is white, 10px radius, Floating shadow, scaling in from the top right over 0.24s. Items are 6px rows that fill Desk Mist and nudge 2px right on hover; Log out is red and fills solid red on hover.
- **Breadcrumbs:** 0.875rem muted list separated by slashes.
- **Footer:** hairline top border over 85% Warm Paper, muted 0.9rem links.

### Alert Stack
Fixed bottom-right stack (up to 380px wide) of white 8px toasts with the Floating shadow. Each has a 30px tinted icon square (navy for info, green for success, red for error), a title in ink, an optional message and link-button actions, a close button, and a 3px timer bar along the bottom edge that pauses on hover or focus. Toasts arrive by rising 14px from a slight blur.

### Beams Hero
The home hero sits in the Night Room with a blurred canvas of slowly drifting cyan-to-blue beams (hue 190 to 235) under a pulsing veil. Headline lines come into focus one after another (blur 14px to sharp, 140ms apart), followed by the lede, search and actions rising in. A side column lists the three real database counts as a definition list with coloured swatches; it is omitted entirely if the counts cannot be loaded.

### Journey Timeline
A scroll-linked "from lost to found" sequence. A 2px rail holds a beam that fills downward from Lost Amber to Found Leaf as the section scrolls. Each step has a sticky title (pale until reached, then ink), a circular marker that fills amber for the first step and green afterwards, and a body that sharpens from blur as it is reached. Bodies contain vignettes: white 10px sheets of real interface pieces, each badged "Example" in a small bordered label at the top right so they are never mistaken for live data. Without JavaScript or with reduced motion, every step is simply shown and the rail is full.

### Ambient Layers
- **Sliding Ease ground:** a fixed canvas of navy hairlines every 24px with short dashes sliding in eased waves, around 30fps, paused in hidden tabs, a single still frame for reduced motion.
- **Magnetic cursor** (ported from the earlier Campus Lost & Found project): a 6px navy dot tracks the pointer exactly and a 34px ring (1.5px navy border, 7% navy fill) follows with spring lag, stretching along the direction of travel and shrinking to 85% on press. Over buttons, header links, the brand and the account trigger, the ring wraps the element (its size plus 10px, its radius plus 4px) and the element leans up to 8px toward the pointer. Both turn pale over the dark hero. Hidden over text fields; menu items and disabled controls do not attract it. Fine pointers only, never with reduced motion, and the native cursor always stays visible.
- **Button motion** (same source): on hover a soft band of light sweeps across once (0.7s), the button rises 1px and its icon nudges forward (the plus icon turns 90 degrees); on press it scales to 0.97 in 0.08s. Disabled buttons do none of this.

### Motion
One exponential ease-out (`cubic-bezier(0.16, 1, 0.3, 1)`) drives state changes and entrances; a symmetric ease-in-out (`cubic-bezier(0.65, 0, 0.35, 1)`) is used only for the outgoing route fade. Lists that arrive together stagger once at 55ms per item, capped at eight items. Route changes cross-fade (160ms out, 280ms in) and item media and titles morph over 420ms. Lenis inertial scrolling (1.05s, quartic ease-out) runs only on fine pointers without reduced motion; each new page starts at the top instantly.

**The Reduced Motion Rule.** Every animation has a reduced-motion path: entrances become a 0.3s fade, hover transforms and view transitions are removed, the magnetic cursor, button sweep and lift, Lenis and toast timers are switched off, and canvases draw a single still frame.

## Do's and Don'ts

### Do:
- **Do** use Counter Navy for the service's own actions and Lost Umber / Found Forest only for lost and found actions and marks.
- **Do** pair every lost or found colour with the word LOST or FOUND, or another text cue.
- **Do** keep corners at 6px by default, 4px for small inline marks, 10px for floating sheets.
- **Do** set headings and numerals in Bricolage Grotesque and all reading and input text in Atkinson Hyperlegible Next.
- **Do** keep resting surfaces at the Resting shadow and reserve Lift for hover.
- **Do** use the shared ease-out for motion and provide a reduced-motion path for every new effect.
- **Do** show real data or nothing: hide a count or panel that cannot load rather than filling it.
- **Do** badge any illustrative interface sample as an example, as the journey vignettes do.
- **Do** draw icons as 24-grid stroke SVGs in currentColor, hidden from screen readers when decorative.

### Don't:
- **Don't** use purple, purple gradients, or beams outside the cyan-to-blue range.
- **Don't** make pill-shaped or fully rounded buttons or tags.
- **Don't** use emoji as icons.
- **Don't** show fake reviews, testimonials, metrics, counters or placeholder content.
- **Don't** use AI-generated stock photos; item photos come from reports, otherwise use the category icon disc.
- **Don't** write vague hero text; the hero asks the user's actual question.
- **Don't** use em dashes in interface copy.
- **Don't** add coloured borders to cards other than the item card's 3px top edge; that edge is a deliberate exception from the owner's reference.
- **Don't** use hard offset shadows.
- **Don't** let any decorative effect (beams, Sliding Ease, magnetic cursor) carry information.
