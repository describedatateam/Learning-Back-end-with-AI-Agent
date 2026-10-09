# Describe Design System

**Version 1.1 · 2026-10-07** (no emojis, icon set, Arabic and RTL) · Built on the colours already in `learn/templates/learn/base.html`, so the current exercise pages fit in without a redesign.

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

## 3. The platform promise (copy that appears in the product)

Shown on the sign-up page and on first login, then always reachable from the footer as **"How this works"**:

1. **Pick a path or make your own.** Job paths take you toward a role. Skill paths teach one thing well.
2. **Learn by building.** Each chapter ends in real code that is checked automatically.
3. **Remember it.** Short flashcards come back right before you'd forget them.
4. **Bring your own project.** Upload or write its requirements (SRS), and get a step-by-step walkthrough.
5. **Leave with proof.** Every finished path adds a project to your public portfolio.

Every path card repeats the promise in miniature, each item with its icon: **time · what you'll build · skills you'll gain** (icons: `clock`, `hammer`, `target`).

## 4. Colour

Existing tokens, kept as they are. Light and dark are both supported.

| Token | Light | Dark | Use for |
|---|---|---|---|
| `--bg` | `#f6f7f9` | `#11151c` | Page background |
| `--surface` | `#ffffff` | `#181d26` | Cards, panels |
| `--border` | `#dde1e7` | `#2c3442` | Card edges, dividers |
| `--text` | `#1c2330` | `#e4e8ef` | Main text |
| `--muted` | `#5d6778` | `#9aa4b5` | Secondary text, hints |
| `--accent` | `#2f6fdf` | `#6b9bf5` | Primary buttons, links, active progress |
| `--accent-soft` | `#e5eefc` | `#1d2a42` | Selected tabs, highlighted cards |
| `--ok` / `--ok-soft` | `#1f8a4c` / `#e3f4ea` | `#4cc281` / `#173024` | Passed, done, correct |
| `--bad` / `--bad-soft` | `#c43d3d` / `#fbe7e7` | `#f07070` / `#3a1c1f` | Failed tests, errors |
| `--warn` / `--warn-soft` | `#a86a00` / `#fdf1dc` | `#e8b04a` / `#362a14` | Gaps in an SRS, cards overdue |
| `--xp` / `--xp-soft` | `#8a4fe0` / `#f1e8fd` | `#b38cff` / `#2a1f42` | XP, streaks, achievements only |
| `--code-bg` / `--code-text` | `#0f1623` / `#e3e8f0` | same | Code editor and code blocks |

**Rules**
- One accent per screen. If two things are blue, one of them shouldn't be.
- Purple (`--xp`) is reserved for rewards, so it stays special.
- Colour never carries meaning on its own: a passed test is green **and** has a `check` icon.

**New tokens to add on Day 1** (two path types need their own quiet identity):

| Token | Light | Dark | Use for |
|---|---|---|---|
| `--job` | `#0f766e` | `#4fd1c5` | Job path badges and card top border |
| `--skill` | `#2f6fdf` (same as accent) | `#6b9bf5` | Skill path badges |

## 5. Type

| Role | Size / weight | Example |
|---|---|---|
| Page title | 28px / 700 | "Backend Developer" |
| Section title | 20px / 650 | "Course 2: Models and Databases" |
| Card title | 16px / 600 | "Migrations" |
| Body | 15px / 400, line height 1.6 | Lesson text |
| Small / meta | 13px / 500, `--muted` | "4 courses · 30 days" |
| Code | 14px, `--mono` | Editor, inline code |

- Font: the system UI font stack (fast, no download): `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.
- Keep lines under about 70 characters in lessons.
- Sentence case everywhere ("Generate a path", not "Generate A Path").

## 6. Space, shape, depth

- **Spacing scale:** 4, 8, 12, 16, 24, 32, 48px. Inside cards: 16px. Between cards: 16px. Between sections: 32px.
- **Radius:** `--radius: 10px` for cards; 8px for buttons and inputs; 999px for tags.
- **Shadows:** almost none. Cards use a 1px `--border`; only hover adds `0 2px 8px rgb(0 0 0 / 0.06)`.
- **Layout:** content max width 1080px; lessons 720px. One column on phones (under 640px), two or three card columns above.

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
- Bar: 6px tall, `--border` track, `--accent` fill, `--ok` when 100%.
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

## 7a. Icons (no emojis)

The interface uses **no emojis**, anywhere: not in buttons, notices, headings or AI-generated content (the Gemini prompts say so too). Icons are used only where they help someone scan or recognise something faster.

- **Set:** [Lucide](https://lucide.dev) (free, open source, consistent outline style). Copy the SVGs we use into `static/icons/` so nothing loads from outside the site.
- **Size:** 16px inline with text, 20px in buttons and navigation, 24px on cards. Stroke width 1.75.
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
| XP / Streak | `zap` / `flame` |

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

**Next:** Day 1 turns this file into a shared stylesheet (`static/css/tokens.css` plus components) and builds the home page with it. Copy this file into the repo as `docs/design-system.md` in that session so it stays with the code.
