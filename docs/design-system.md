# Platform Design System

**Version 2.0 · 2026-10-08** · Adopts the "Describe" design system and dashboard mockup (`plans/reference/dashboard-mockup.png`, source text in `plans/reference/describe-design-system-v1-source.md`): indigo palette, Inter, dark navy sidebar, learning-cockpit home. Everything from v1.1 that the new system didn't cover stays: no emojis, Lucide icons, Arabic and RTL, dark mode, the promise and discovery rules.

**Token names stay the same as Day 1** (`--accent`, `--ok`, ...), only their values change, so existing pages pick up the new look without template edits. Where the mockup breaks our rules, our rules win: its emojis (wave, flame, star) become Lucide icons, the Python logo becomes a Lucide icon, and the mountain illustrations are optional extras for later.

The product name is **Describe** (decided 2026-10-08), a product of the user's agency, so the brand can be reused for other products later. It replaces "Dev Lab" from Day 1.

---

## 1. The idea in one line

> **Calm on the surface, clear about the promise, and the rest reveals itself as you learn.**

Learners should always know two things: **what the platform will give them**, and **the one next step to take**. Everything else waits until they need it.

## 2. Principles

| Principle | What it means on screen |
|---|---|
| **One next step** | Every page has one primary button (Resume, Start, Review). Other actions are secondary or tucked away. |
| **Promise up front** | Before a learner starts anything, they see what they will get: time, what they'll build, skills gained. No surprises. |
| **Reveal as you go** | Features appear when they become useful. Flashcards show once there are cards due; the portfolio fills in as projects finish; locked chapters show their title, not their contents. |
| **Learn by doing first** | Exercises and projects are the main thing. Lessons, slides and videos support them and never compete with them visually. |
| **Progress you can feel** | Progress bars, ticks and XP sit on every path and chapter, and are small, honest and never noisy. |
| **Quiet by default** | Neutral backgrounds and one accent colour. Colour carries meaning (done, error, XP), not decoration. |
| **Show where they are** | Every learning screen answers "Where am I?" with path position, chapter label and progress. The home page is a learning cockpit, not a course list. |
| **Data changes what happens next** | Show a number only if it helps the learner decide something. Call it "progress" or "skill path progress", never "knowledge" or "mastery", until the data backs that up. |

## 3. The platform promise (copy that appears in the product)

Shown on the sign-up page and on first login, then always reachable from the footer as **"How this works"**:

1. **Pick a path or make your own.** Job paths take you toward a role. Skill paths teach one thing well.
2. **Learn by building.** Each chapter ends in real code that is checked automatically.
3. **Remember it.** Short flashcards come back right before you'd forget them.
4. **Bring your own project.** Upload or write its requirements (SRS), and get a step-by-step walkthrough.
5. **Leave with proof.** Every finished path adds a project to your public portfolio.

Every path card repeats the promise in miniature, each item with its icon: **time · what you'll build · skills you'll gain** (icons: `clock`, `hammer`, `target`).

## 4. Colour

Indigo primary, emerald success, amber motivation, dark navy navigation (from the new system). Same token names as Day 1. The new system's raw colours are used for fills and bars; text and button colours are one shade darker where the raw colour fails WCAG AA (for example, white text on `#6366F1` is only 4.5:1 at best, so buttons use `#4F46E5`).

| Token | Light | Dark | Use for |
|---|---|---|---|
| `--bg` | `#f8fafc` | `#0b1220` | Page background |
| `--surface` | `#ffffff` | `#111a2e` | Cards, panels |
| `--surface-subtle` (new) | `#f1f5f9` | `#16213a` | Secondary panels, table stripes, metric icon wells |
| `--border` | `#e2e8f0` | `#24304a` | Card edges, dividers |
| `--text` | `#0f172a` | `#e2e8f0` | Main text |
| `--muted` | `#64748b` | `#94a3b8` | Secondary text, hints, metadata |
| `--accent` | `#4f46e5` | `#818cf8` | Primary buttons, links, focus ring (dark theme: button text `#0b1220`) |
| `--accent-bar` (new) | `#6366f1` | `#818cf8` | Progress bar fill, active journey node |
| `--accent-soft` | `#e0e7ff` | `#1e1b4b` | Selected tabs, highlighted cards, "in progress" badge |
| `--ok` / `--ok-soft` | `#047857` / `#d1fae5` | `#34d399` / `#063b2c` | Passed, done, correct (text and icons) |
| `--ok-bar` (new) | `#10b981` | `#34d399` | Completed bars, "Generate another exercise" button fill |
| `--bad` / `--bad-soft` | `#dc2626` / `#fee2e2` | `#f87171` / `#3b1518` | Failed tests, errors |
| `--warn` / `--warn-soft` | `#b45309` / `#fef3c7` | `#fbbf24` / `#3a2a0a` | Needs practice, gaps in an SRS, cards overdue |
| `--xp` / `--xp-soft` | `#b45309` / `#fef3c7` | `#fbbf24` / `#3a2a0a` | XP, streaks, achievements (amber now; always with `zap`, `flame` or `award` so it never reads as a warning) |
| `--info` (new) | `#0369a1` | `#38bdf8` | Informational notices |
| `--job` | `#0f766e` | `#2dd4bf` | Job path badges and card top border |
| `--skill` | `#4f46e5` (same as accent) | `#818cf8` | Skill path badges |
| `--nav-bg` (new) | `#0b1b36` | `#070f20` | Sidebar background |
| `--nav-bg-2` (new) | `#102544` | `#0b1b36` | Sidebar progress box, bottom nav on phones |
| `--nav-active` (new) | `#1f2d5c` | `#1f2d5c` | Active sidebar item |
| `--nav-text` (new) | `#cbd5e1` | `#cbd5e1` | Sidebar text; active item text is `#ffffff` |
| `--code-bg` / `--code-text` | `#0f172a` / `#e2e8f0` | same | Code editor and code blocks |

**Rules**
- One accent per screen. If two things are indigo, one of them shouldn't be.
- Amber means "effort and reward" (XP, streaks) or "needs attention" (warnings); the icon and label say which.
- Colour never carries meaning on its own: a passed test is green **and** has a `circle-check` icon **and** says "Passed".
- The sidebar is dark in both themes.

## 5. Type

| Role | Size / weight / line height | Example |
|---|---|---|
| Display (home greeting) | 32px / 700 / 40px (24px on phones) | "Good evening, Sara" |
| Page title | 24px / 700 / 32px | "Backend Developer" |
| Section / card title | 16px / 600 / 24px | "Your learning journey" |
| Data value | 28px / 700 / 1 | "48 / 62" |
| Body (dashboard) | 14px / 400 / 22px | Card text |
| Body (lessons) | 16px / 400 / 1.6 | Lesson text |
| Small / meta | 12px / 500 / 18px, `--muted` | "8 lessons · 21 exercises" |
| Code | 14px, `--mono` | Editor, inline code |

- Latin font: **Inter** (variable, weights 400 to 700), self-hosted in `static/fonts/` so it works on PythonAnywhere's free plan and loads fast. Fallback: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.
- Arabic font: **IBM Plex Sans Arabic**, self-hosted too (Inter has no Arabic letters). See 7b.
- Numbers in metric cards use `font-variant-numeric: tabular-nums` so they line up.
- Keep lesson lines under about 70 characters. Sentence case everywhere. Don't overuse bold.

## 6. Space, shape, depth

- **Spacing scale (4px base):** 4, 8, 12, 16, 20, 24, 32, 40, 48, 64px. Card padding 20px (16px on phones). Gaps between cards 16px. Between page sections 24 to 32px.
- **Radius:** cards `--radius-card: 14px`; buttons and inputs `--radius-control: 9px`; small chips 6px; badges and pills 999px.
- **Shadows:** `--shadow-sm: 0 1px 2px rgb(15 23 42 / 0.05)` on cards (with the 1px border), `--shadow-md: 0 4px 12px rgb(15 23 42 / 0.07)` on hover, `--shadow-lg: 0 12px 32px rgb(15 23 42 / 0.10)` for menus and dialogs only.

## 6a. Layout and navigation

**App shell (from the mockup)**
- **Laptop and desktop (1024px and up):** fixed dark sidebar, 248px wide, on the inline-start side (left in English, right in Arabic). Content area padding 32px, dashboard max width 1440px, lessons 720px.
- **Tablet (640 to 1023px):** sidebar collapses to a 72px icon rail with tooltips; a menu button expands it.
- **Phone (under 640px):** no sidebar. A bottom navigation bar with 5 items (Home, Paths, Flashcards, Project, Portfolio) in `--nav-bg-2`, plus a top bar with the language switch and profile. Single column cards; the journey scrolls sideways; the primary action sticks to the bottom above the nav.
- **Exercise page:** the sidebar collapses to the icon rail so the editor gets the room (split view on desktop, stacked on phones).

**Sidebar contents**
- Top: product name and logo mark.
- Items (icon 18px + label): Home `house`, Paths `compass`, My project `file-text`, Flashcards `layers`, Portfolio `briefcase`. The mockup's separate Learn, Pathways and Courses all live under **Paths**. AI tutor `bot` and Analytics `chart-line` are added only when those pages exist.
- Bottom: a progress box (level and XP bar, in `--nav-bg-2`), then the learner's name, language switch and settings.
- Active item: `--nav-active` background, white icon and text, 9px radius. No bright blocks.
- **Dashboard grid:** 12 columns. Typical splits: main 8 + side 4, journey 7 + activity 5. Sizes follow importance; not every card is the same size.

## 7. Components

### Buttons
| Type | Look | When |
|---|---|---|
| Primary | `--accent` fill, white text | The one next step on the page |
| Secondary | `--accent` outline | Other useful actions (Hint, Slides) |
| Quiet | Text only, `--muted` | Low-stakes actions (Skip, Show solution) |
| Danger | `--bad` outline | Reset code, delete project |

Minimum height 40px (44px on phones). Labels are verbs: **Resume**, **Run tests**, **Generate**.

### Cards
- **Path card:** type badge (Job / Skill), title, the three-part promise line, progress bar once started.
- **Chapter card:** status icon (`circle` not started, `circle-dot` in progress, `circle-check` done, `lock` locked), title, time estimate.
- **Next-step card (home page):** the biggest card on the page with one primary button.

### Progress
- Bar: 8px tall, fully rounded, `--surface-subtle` track, `--accent-bar` fill, `--ok-bar` when 100%.
- Ring (metric cards only): 48px circle, 5px stroke, percentage in the middle.
- Status badges (pill, icon + label): Completed (`--ok`), In progress (`--accent`), Needs practice (`--warn`), Locked (`--muted`).
- Always show the number beside it ("45%" or "5 of 11 chapters").

### Tags and badges
Small pills: `Job path`, `Skill path`, `Beginner`, `AI-generated`. Generated paths always carry **AI-generated**, so learners know where content came from.

### Flashcard
Centered card, front shows a question; tap or Space to flip. Four answer buttons: **Again · Hard · Good · Easy**, each showing when the card will return ("10 min", "2 days").

### Notices
- **Info** (`--accent-soft`): tips, "New: flashcards unlocked".
- **Success** (`--ok-soft`): "All tests passed. +50 XP".
- **Warning** (`--warn-soft`): "Your SRS has no data models yet."
- **Error** (`--bad-soft`): "Couldn't generate the path. Try again."
One notice at a time; they never block the page.

### Empty states
Every empty screen explains what will appear there and offers the one action to fill it:
- Portfolio: "Your finished projects will live here. Finish your first path to add one." **Explore paths**
- Flashcards: "No cards due. Nice. New cards arrive as you finish chapters."
- My project: "Working on something? Describe it or upload its SRS, and we'll walk you through it."

### Learning cockpit (home page)

The home page from the mockup, built from data we actually have. Each block lists when its data exists, so no block shows made-up numbers.

| Block | What it shows | Data ready |
|---|---|---|
| Greeting | "Good evening, Sara" and one encouraging line about the next milestone. No emoji. | Day 2 (accounts) |
| Path hero | Current path name and one-line promise, progress bar with %, time remaining, next milestone, **Continue learning** button (the page's one primary action). Path icon from Lucide instead of a logo; illustration optional later. | Day 3 |
| Metric cards (4) | Lessons completed, Exercises passed (each with a ring), Streak (`flame`), Total XP and level (`zap`). | Day 2 (per-user progress and XP) |
| Your learning journey | Vertical list of the path's courses or chapters: status icon, title, "8 lessons · 21 exercises", %. Current one highlighted, locked ones muted. "View full path" link. | Day 3 |
| Recent activity | Last 5 events: icon, what happened, topic, time ago, XP earned. | Day 2 event log |
| Skill path progress | One row per skill path in the job path, with icon and bar. Named "Skill path progress" (completion), not "skill level", until concept tracking exists. | Day 3 |
| Encouragement card | Navy card with one line of text. Optional. | Any time |

Empty states follow section 7: a new learner sees the greeting, the path hero with **Start**, and the promise, not a wall of zeros.

### Later screens (designed in the mockup, built after the 2 weeks)
- **Exercise page:** instructions, Tests and Hints tabs on the start side, editor and console on the end side, "Exercise 2 of 5" and **Generate another exercise** (`--ok-bar` button, `sparkles` icon). Today's exercise page only picks up the new tokens.
- **Attempt history table:** attempt #, result badge, accuracy, hints, time.
- **Analytics:** tabs Overview, Performance, IDE activity, AI tutor; line chart of progress over time.
- **Profile:** avatar, level, current path, recent achievements (icons, not emojis).

## 7a. Icons (no emojis)

The interface uses **no emojis**, anywhere: not in buttons, notices, headings or AI-generated content (the Gemini prompts say so too). Icons are used only where they help someone scan or recognise something faster.

- **Set:** [Lucide](https://lucide.dev) (free, open source, consistent outline style). Copy the SVGs we use into `static/icons/` so nothing loads from outside the site.
- **Size:** 16px inline with text, 18px in the sidebar, 20px in buttons, 24px on cards and metric wells. Stroke width 1.75.
- **Colour:** `currentColor`, so icons take the colour of their text.
- **Always labelled:** an icon sits next to a text label, or has an `aria-label` when it stands alone (like a close button).
- **Use icons for:** navigation items, path-card promise line, chapter status, chapter resource types (video, slides, lesson, exercise, quiz, flashcards), notices.
- **Don't use icons for:** decoration, headings, or celebrating. Text does that.

| Meaning | Lucide icon |
|---|---|
| Home / Paths / My project / Flashcards / Portfolio | `house` / `compass` / `file-text` / `layers` / `briefcase` |
| Generate with AI | `sparkles` |
| Video / Slides / Lesson / Exercise / Quiz | `play-circle` / `presentation` / `book-open` / `code` / `circle-help` |
| Not started / In progress / Done / Locked | `circle` / `circle-dot` / `circle-check` / `lock` |
| Time / Build / Skills | `clock` / `hammer` / `target` |
| Upload SRS / Warning / Error / Success | `upload` / `triangle-alert` / `circle-x` / `circle-check` |
| XP / Streak / Achievement | `zap` / `flame` / `award` |
| Lessons done / Exercises passed / Activity | `book-check` / `circle-check-big` / `activity` |
| Search / Notifications / Settings | `search` / `bell` / `settings` |
| AI tutor / Analytics / Generate another exercise | `bot` / `chart-line` / `sparkles` |

## 7b. Arabic and right-to-left

The whole platform works in **English and Arabic**, and switching is one click (`English | العربية` in the header and on sign-up).

**Layout**
- Arabic pages set `<html lang="ar" dir="rtl">`; the browser then mirrors the layout.
- CSS uses **logical properties** everywhere: `margin-inline-start` not `margin-left`, `padding-inline-end` not `padding-right`, `text-align: start` not `left`. Then one stylesheet works in both directions.
- Direction-carrying icons flip in RTL (`chevron-right`, `arrow-right`, progress "next"): add `.icon-flip { transform: scaleX(-1); }` under `[dir="rtl"]`. Icons like `check`, `clock`, `play-circle` never flip.
- Progress bars fill from right to left in Arabic.

**Code stays left-to-right**
- Code editor, code blocks, terminal output, test results and file names are always `dir="ltr"`, even on Arabic pages, because Python is written left to right.
- Inline code inside Arabic text is wrapped in `<bdi>` or `<code dir="ltr">` so punctuation doesn't jump.

**Type**
- Arabic font: **IBM Plex Sans Arabic** (Google Fonts, free; pairs cleanly with the system Latin font). Fallback: `"Noto Sans Arabic", Tahoma, sans-serif`.
- Arabic body text: 16px with line height 1.8 (Arabic needs more room than Latin).
- No letter-spacing and no italics on Arabic text (they break letter joining). Use weight for emphasis instead.
- Numbers: Western digits (0-9) in both languages, so code, XP and percentages read the same.

**Words**
- All interface text goes through Django's translation system (`{% translate %}`, `gettext`), with one Arabic file (`locale/ar/LC_MESSAGES/django.po`).
- Keep technical terms in English with an Arabic explanation the first time, e.g. "النموذج (model)". Learners will meet the English terms in real jobs.
- AI content (generated paths, flashcards, SRS walkthroughs, tutor replies) is written in the learner's chosen language; code and identifiers stay English.
- Existing hand-written lessons stay English at first; an Arabic summary per chapter can be generated and reviewed later.

## 8. Discovery: how the journey unfolds

What the learner sees grows with them. This keeps the first visit calm and makes each new feature feel earned.

| Moment | What appears |
|---|---|
| First visit | The promise (5 steps), then one question: "Pick a path or make your own." |
| First chapter started | Home shows the **Continue** card. |
| First chapter finished | Flashcards unlock, with a one-line notice. |
| First course finished | Portfolio page activates with a preview. |
| Any time after week 1 | **My project (SRS)** is suggested on the home page. |
| Path finished | Capstone project unlocks; on completion it's added to the portfolio. |

Navigation still shows every section from day one (so nothing feels hidden), but sections that aren't useful yet show a friendly empty state instead of a blank page.

## 9. Voice and tone

- Talk to the learner as **you**, warmly and plainly, like a patient senior developer.
- Short sentences. Explain jargon the first time ("a migration, the file that updates your database tables").
- Celebrate briefly ("Nice, all tests pass."), never with exclamation-mark piles.
- Errors say what happened and what to do next, never blame.
- Be honest about AI: label generated content and invite learners to report mistakes.

## 10. Accessibility

- Text contrast at least 4.5:1 in both themes (existing tokens meet this; check new ones on Day 1).
- Everything works with a keyboard; visible focus ring: `2px solid var(--accent)` with 2px offset.
- Icons always have a text label or `aria-label`.
- Arabic pages have correct `lang` and `dir` so screen readers use the right voice.
- Respect `prefers-reduced-motion`: no flip or slide animations when it's on.
- Touch targets at least 44px on phones.

## 11. Motion

Small and quick: 150ms ease-out for hover and reveals, 250ms for the flashcard flip. Motion explains a change (a card unlocking), never decorates.

---

**Next:** Day 1 built v1.1 into `static/css/tokens.css` and the home page. Adopting v2.0 means: swap token values and add the new tokens (section 4), self-host Inter (section 5), add the app shell (section 6a), and rebuild the home page as the learning cockpit (section 7). Copy this file over `docs/design-system.md` in the repo in that session. The previous version is in `plans/reference/design-system-v1.1.md`.
