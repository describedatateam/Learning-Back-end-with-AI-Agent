# Put Dev Lab online with PythonAnywhere

This gets Dev Lab running at `https://yourname.pythonanywhere.com`, so you can
use it from any computer or phone. It takes about 20 minutes. Everywhere below,
replace **`yourname`** with your PythonAnywhere username.

> **Why there's a login:** Dev Lab runs the Python code you type. On the open
> internet, anyone could use that to run code on your account, so the online copy
> only works for you after you log in.

> **Before you start:** this guide needs the "Prepare Dev Lab for PythonAnywhere"
> pull request merged into `master` on GitHub (and "Add Google Gemini as a backup
> tutor" if you want the free tutor). Without the first one, the online copy has no
> login, so don't put it online until it's merged.

## What works online

| feature | online? |
|---|---|
| lessons, editor, colours, autocomplete | ✅ |
| Run tests, ▶ single test, Run selection | ✅ (free accounts get a limited amount of CPU time per day, so heavy use can make runs slow) |
| XP, quizzes, Notebook pages you already wrote, 📑 Slides | ✅ |
| **Study tutor and "Write my page"** | ⚠️ Needs an AI key in `.env`, because Claude Code (and so your Claude Code login) isn't available on PythonAnywhere. The free option is a **Google Gemini** key (`GEMINI_API_KEY`) from <https://aistudio.google.com/apikey>; an Anthropic API key works too. Free PythonAnywhere accounts can only reach an approved list of websites, so if the tutor says it can't connect, check that the AI's address (`generativelanguage.googleapis.com` for Gemini, `api.anthropic.com` for Claude) is on PythonAnywhere's allowlist, or use a paid account. |

## 1. Create an account

Sign up at <https://www.pythonanywhere.com> (the free "Beginner" plan is fine).
Your username becomes your web address.

## Already tried before? Start here

If you set up a PythonAnywhere web app before Dev Lab was on GitHub, it showed
only the old project. Reuse your account and web app, but start the code fresh:

1. Open **Consoles → Bash** and move the old copy out of the way (nothing in it is
   needed):

   ```bash
   ls
   mv Learning-Back-end-with-AI-Agent old-attempt
   ```

   Use whatever the old folder is called in the `ls` list. If the `mv` says "No such
   file", there's no old copy, so skip it.
2. Do **steps 2, 3 and 4** below as written.
3. In step 5, **don't** click "Add a new web app": open your existing one on the
   **Web** tab and update it instead:
   - **Python version:** 3.12 (Django 5.2 needs 3.10 or newer).
   - **Source code**, **Virtualenv**, **Static files** and **Force HTTPS** as listed in step 5.
   - **WSGI configuration file:** replace *everything* in it with the code from step 5.
     If you first used PythonAnywhere's "Django" option, the old file points to a
     different project (often `mysite.settings`), which is why it showed the wrong site.
   - Click **Reload**.
4. When it works, you can delete `old-attempt` (and any `mysite` folder the "Django"
   option made) from the **Files** tab.

## 2. Get the code

Open **Consoles → Bash** and run:

```bash
git clone https://github.com/describedatateam/Learning-Back-end-with-AI-Agent.git
cd Learning-Back-end-with-AI-Agent
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If the repository is private, GitHub will ask for a password: use a
[personal access token](https://github.com/settings/tokens) instead of your password.

## 3. Create the settings file

Still in the console, make a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Then create the file `.env` with `nano .env`, paste this in (with your key and
username), and save with **Ctrl+O, Enter, Ctrl+X**:

```
DJANGO_SECRET_KEY=paste-the-key-from-the-command-above
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourname.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://yourname.pythonanywhere.com
LEARN_REQUIRE_LOGIN=True
# Optional, for the study tutor (remove the # to turn one on):
# GEMINI_API_KEY=your-free-key-from-google-ai-studio
# ANTHROPIC_API_KEY=sk-ant-...
```

## 4. Prepare the database and your login

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

`createsuperuser` asks for a username, email (optional) and password. **This is the
login you'll use for the site.**

## 5. Create the web app

1. Open the **Web** tab and click **Add a new web app**.
2. Click **Next**, choose **Manual configuration** (not the "Django" option), then
   **Python 3.12**.
3. On the web app's page, set these:
   - **Source code:** `/home/yourname/Learning-Back-end-with-AI-Agent`
   - **Virtualenv:** `/home/yourname/Learning-Back-end-with-AI-Agent/.venv`
   - **Static files:** add URL `/static/` → directory
     `/home/yourname/Learning-Back-end-with-AI-Agent/staticfiles`
   - **Force HTTPS:** turn it on.
4. Click the **WSGI configuration file** link, delete everything in it, paste this,
   and save:

   ```python
   import os
   import sys

   path = '/home/yourname/Learning-Back-end-with-AI-Agent'
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```

5. Click the green **Reload** button at the top of the Web tab.

Open `https://yourname.pythonanywhere.com`, log in with the account from step 4,
and you're in.

## Bring your progress along (optional)

Your XP, passed exercises, tutor chats and Notebook pages live in `db.sqlite3` on
the computer where you've been studying. To continue online from where you are:

1. In PythonAnywhere's **Files** tab, open `Learning-Back-end-with-AI-Agent/` and
   upload your local `db.sqlite3` (it replaces the empty one).
2. In a Bash console: `cd Learning-Back-end-with-AI-Agent && source .venv/bin/activate && python manage.py migrate`
3. Your uploaded database doesn't contain the login from step 4, so run
   `python manage.py createsuperuser` again.
4. Reload the web app.

From then on, the online copy is your main one: progress made locally won't sync
to it automatically.

## Updating after new changes

```bash
cd ~/Learning-Back-end-with-AI-Agent
source .venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Then click **Reload** on the Web tab.

## If something goes wrong

The **Web** tab links to an **error log**: the last lines usually say what broke.

| you see | fix |
|---|---|
| "Bad Request (400)" | `DJANGO_ALLOWED_HOSTS` in `.env` doesn't match your address exactly. |
| "CSRF verification failed" when logging in | `DJANGO_CSRF_TRUSTED_ORIGINS` must be `https://yourname.pythonanywhere.com`. |
| The admin login page has no styling | Run `collectstatic` again and check the `/static/` mapping in step 5. |
| "Something went wrong" page | Read the error log; after any change to `.env`, click **Reload**. |
| Run tests says it took too long | You've used up the free CPU time for today; it resets daily. |

Free web apps must be renewed every 3 months: PythonAnywhere emails you, and you
click **Run until 3 months from today** on the Web tab.
