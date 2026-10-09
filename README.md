# Django Backend Bootcamp (30 days)

A beginner-friendly four-week path from Python web fundamentals to a tested Django REST Framework Task Management API backed by SQLite.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `/api/health/` for the public health check and `/admin/` for admin. API endpoints require Basic or session authentication:

- `GET, POST /api/projects/`; detail supports `GET, PATCH, PUT, DELETE`
- `GET, POST /api/tasks/`; detail supports `GET, PATCH, PUT, DELETE`

Task filters include status, priority, project, and due_date. Lists support search,
ordering, and pagination with page_size up to 50. Every query is restricted to the
authenticated user.

## Describe: interactive exercises

After `migrate` and `runserver`, open <http://127.0.0.1:8000/> (it goes straight to
Describe at `/learn/`). Learning needs an account, so first create yours with
`python manage.py createsuperuser` and sign in. Other learners sign up at
`/accounts/signup/` with an invite code: make codes in `/admin/` under **Invite codes**
(each has a number of uses and an optional expiry date). Every account has its own
progress, XP, tutor chats and notebook, stored in the local `db.sqlite3` (not in git).
Each action (a test run, pass, quiz, tutor question, opened solution) also adds a
row to the **Learning events** log in the admin, with the time spent on the page.

The code runner gets none of the site's secrets, can't open files outside its own
temporary folder, start programs or use the network, and is capped at 20 seconds of
CPU and 512 MB of memory. It's a safety net for people you invite, not a full sandbox.

**Use it from anywhere:** [DEPLOY_PYTHONANYWHERE.md](DEPLOY_PYTHONANYWHERE.md) puts it online
behind a login, step by step.

Each exercise page has a **📑 Slides** button that opens that lesson's deck. The decks
are in `materials/out/pdf/` (PDF) and `materials/out/decks/` (PowerPoint). It has 17
hands-on exercises that follow the four weeks below. Each one has a short lesson,
an in-browser code editor, hints, a quiz and a reference solution.
**Run tests** grades your code against real Django/DRF tests in an isolated
subprocess, and your progress is saved in the local database.

You earn XP for passing tests, completing exercises, quizzes and daily practice. XP
raises your level (Intern → Backend Architect), a daily streak tracks how many days
in a row you've practised, and there are 11 badges to unlock. The XP rules are in
`learn/gamification.py`.

The editor uses VS Code Dark+ colors with colored bracket pairs, closes brackets and
quotes as you type, and suggests Python and Django names (Ctrl+Space). Shortcuts:
**Ctrl+Enter** runs all tests, **Shift+Enter** runs the highlighted code (or the
current line) in the Console tab, and **Ctrl+/** toggles comments. Each test has a
▶ button to run just that one. Single-test runs save your code but don't award XP;
a full run does.

Running code is only allowed from localhost, because it executes the Python you
submit. Exercises live in `learn/content/<NN-slug>/` (`instructions.md`,
`starter.py`, `solution.py`, `grader_tests.py`, `meta.json`). `python manage.py test learn`
checks that every reference solution passes and every starter fails.

### Study tutor (AI)

Every exercise has a **Tutor ✨** tab, and `/learn/tutor/` is for general questions.
The tutor is powered by Claude. It sees the lesson, your current code and your latest
test results, and it guides you with explanations and hints rather than handing over
the answer. Conversations are saved per exercise and can be cleared from the chat.

The tutor reaches Claude in one of two ways, chosen automatically:

- **Claude Code login (no API key needed).** If the Claude Code extension is installed,
  the tutor runs its bundled `claude.exe` in the background with the account you're
  signed into. Questions count toward your Claude plan's usage limits. The tutor finds
  the newest installed version automatically, or you can set `LEARN_CLAUDE_CLI` to the
  path of `claude.exe`. It runs with all tools disabled and your plugins and hooks
  turned off, so it can only answer questions.
- **Anthropic API key.** If `ANTHROPIC_API_KEY` is set in `.env`, the tutor uses the
  API instead, billed to your Anthropic account.

- **Google Gemini (free backup).** Add `GEMINI_API_KEY=...` to `.env`, using a free key
  from <https://aistudio.google.com/apikey>. If Claude fails before answering (not
  signed in, usage limit, no key), Gemini answers instead and the chat says so. With
  only a Gemini key, Gemini is the tutor. The free tier has daily limits, and Google
  may use free-tier prompts to improve its products.

Optional `.env` settings: `LEARN_TUTOR_BACKEND=claude_code`, `api` or `gemini` forces
one, `LEARN_TUTOR_MODEL` picks the Claude model, and `LEARN_GEMINI_MODEL` picks the
Gemini model (default `gemini-flash-latest`).

### Notebook

The **Notebook 📓** tab has one page per passed exercise. Each page covers the tools
you learned (with examples), where they're used, what you found difficult and how
you solved it, and your final code. Pages are written by the tutor's AI from your
chats and test history: click **✨ Write my page** after passing. `python manage.py
export_notebook USERNAME` saves that learner's pages as one HTML file (`materials/out/notes/00-my-learning-journal.html`).

## Study materials (slides, notes, further reading)

`materials/` builds a slide deck and a study-notes page for every exercise:

- `materials/decks/*.json`: slide content, one file per exercise.
- `materials/resources/*.json`: checked links for further learning.
- `learn/content/*/instructions.md`: the lessons (see `learn/content/LESSON_STYLE.md`).

```bash
pip install -r materials/requirements.txt
python materials/build_materials.py        # -> materials/out/decks/*.pptx and notes/*.html
python materials/export_pdfs.py            # -> materials/out/pdf/*.pdf (needs PowerPoint)
python materials/preview_deck.py materials/out/decks/01-http-requests.pptx preview/   # slide images
```

**NotebookLM:** add the study-notes Google Docs from Drive, and upload the PDFs from
`materials/out/pdf/` with "Upload source".

## Learning path

Work through `lessons/week-1` through `lessons/week-4` in order; each day has a
lesson and exercise. Week 4 contains nine days so the path totals 30 days. Weekly
reviews are in `assessments/`, including `final.md`.

## Development commands

```bash
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py test
```

SQLite is the default for learning. Configure DJANGO_SECRET_KEY, DJANGO_DEBUG, and
DJANGO_ALLOWED_HOSTS in `.env`; never commit real secrets. For production, use a
secret manager, managed database, HTTPS, and a production WSGI/ASGI setup.
