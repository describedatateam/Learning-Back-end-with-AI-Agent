# Health checks & logging

## The big idea

When an app runs in production, nobody sits and watches it. Instead, other
programs check on it all the time. They visit a special address, usually
`/health/`, every few seconds and ask "are you OK?". That address is a **health
check**.

Who asks? Often a **load balancer**: a program that sits in front of several copies
of your server and shares the visitors between them. Imagine three copies are
running and one loses its connection to the database. If its health check says
"not OK", the load balancer stops sending visitors to it, and they go to the two
healthy copies instead. Deployment tools and uptime monitors (services that email
you when your site is down) call health checks too.

It's like a nurse checking a patient's pulse: asking "how are you?" isn't enough,
you have to actually **measure** something. This project's `/health/` view always
answers `ok`, even when the database is down, which makes it useless. Yours will
really run a tiny query on the database.

When something does go wrong, a person needs to find out **why**. That's what
**logging** is for: the app writes a note about the problem into its log, like a
ship's logbook, so a developer can read it later. The health check's public answer
stays short, and the details go into the log.

## New words

| word | meaning |
|---|---|
| **health check** | An address that other programs call to ask "is this server working?". |
| **load balancer** | A program that shares incoming visitors between several copies of your server. |
| **dependency** | Something your app needs in order to work, like the database. |
| **status code** | The number at the top of every response. Programs read it to know what happened. |
| **503 Service Unavailable** | "I'm running, but I can't do my job right now. Try later, or try another server." |
| **log** | The app's diary: lines of text describing what happened, for developers to read. |
| **logger** | The object you write log lines with, like `logger.error("...")`. Each logger has a name. |
| **log level** | How serious a log line is: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| **traceback** | The "Traceback (most recent call last): ..." report that shows where an error happened. |
| **exception** | Python's word for an error that happens while code runs, like `ValueError`. |

### Why 503, and not 200 or 500?

Status codes come in families: `2xx` means success, `4xx` means "the client did
something wrong", `5xx` means "the server has a problem".

- **200** would be a lie: the load balancer would keep sending visitors to a broken
  server.
- **500 Internal Server Error** usually means "my code crashed", a bug.
- **503 Service Unavailable** says exactly the right thing: "I'm alive, but a
  dependency is down, so don't send me traffic for now". Load balancers read the
  **number**, not the text, so the number has to be right.

## What your code receives and returns

**The tests build a fake request and call your view directly**, like this:

```python
# from the tests (they use Django's RequestFactory to make the request)
response = views.health(factory.get("/health/"))
```

So `request` is a normal Django request object for `GET /health/`. Here's what
the tests expect:

| test | situation | expected response |
|---|---|---|
| 1 | the database works | status **200**, body `{"status": "ok", "checks": {"database": "ok"}}` |
| 2 | the database is down | anything **but** 200 (so you must really query it) |
| 3 | the database is down | status **503**, body `{"status": "error", "checks": {"database": "error"}}`, and an `ERROR` line in the log |
| 4 | the database is down | the log line includes the **traceback** |
| 5 | the database is down | the body does **not** contain the secret error details |
| 6 | a `POST /health/` request | status **405** (Method Not Allowed) |

How do the tests make the database "go down"? They swap the `connection` object in
your file for a fake one. When your code calls `connection.cursor()` on the fake,
it raises an `OperationalError` with the message
`could not connect to server: password=hunter2`.

Look at that message: it contains a password! That's why test 5 checks that
`hunter2` is **not** in your response. Error messages often contain secrets, so
they belong in the log, never in a public response.

> The starter code runs, but always answers `{"status": "ok"}` with status 200,
> whatever happens. Keep `from django.db import DatabaseError, connection` at the
> top of the file: the tests replace `connection` there to fake the outage.

## Tools you'll use

### `with connection.cursor() as cursor:` and `cursor.execute(...)`

- `connection` is Django's link to the database. `connection.cursor()` opens a way
  to send it raw SQL, and `with ... as cursor:` closes it again when the block ends.
- `cursor.execute("SQL here")` sends one SQL command. A tiny query like
  `SELECT 1` is the cheapest way to prove "the database answers".

```python
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT 2 + 3")
    print(cursor.fetchone())   # (5,)
```

### `try` / `except DatabaseError:`

- Code inside `try:` runs normally. If it raises an error of the type named in
  `except`, Python jumps into the `except` block instead of crashing.
- `DatabaseError` is the **family** name for all database errors. `OperationalError`
  (the one the tests raise) is one member of that family, so `except DatabaseError:`
  catches it.

```python
from django.db import DatabaseError, OperationalError

print(issubclass(OperationalError, DatabaseError))   # True: it's part of the family
```

- Common mistake: opening the cursor **before** the `try`. In the tests, it's
  `connection.cursor()` itself that fails, so that line must be inside `try:`.

### Loggers: `logging.getLogger(__name__)`

- Your file already creates one at the top: `logger = logging.getLogger(__name__)`.
  `__name__` is the name of the current file without `.py`, so in `views.py` the
  logger is called `"views"`. The tests listen to exactly that logger.
- Write a line with `logger.info(...)`, `logger.warning(...)`, `logger.error(...)`.
  Without extra setup, only `WARNING` and more serious levels are shown.

```python
import logging

log = logging.getLogger("shop")
log.info("A customer opened the shop")   # not shown: INFO is below WARNING
log.warning("Only 2 cups of tea left")
log.error("The till is broken")
# Only 2 cups of tea left
# The till is broken
```

### `logger.exception("...")`

- Writes an `ERROR` line **and** the traceback of the error being handled. Use it
  only inside an `except` block.
- The program then carries on, so you can still return a response.

```python
import logging

log = logging.getLogger("shop")
try:
    price = int("ten")
except ValueError:
    log.exception("Could not read the price")
print("the program keeps going")
# Could not read the price
# Traceback (most recent call last):
#   File "<selection>", line 5, in <module>
# ValueError: invalid literal for int() with base 10: 'ten'
# the program keeps going
```

- Common mistake: `logger.error("...")` in the `except` block logs the message but
  **not** the traceback, so test 4 fails. Another: putting the error message
  (`str(e)`) into the response instead of the log.

### `JsonResponse(data, status=...)`

- Turns a dictionary into a JSON response. The status is 200 unless you pass
  `status=` as a keyword.

```python
from django.http import JsonResponse

response = JsonResponse({"tea": "hot"}, status=202)
print(response.status_code)   # 202
print(response.content)       # b'{"tea": "hot"}'
```

### `@require_GET`: a decorator

- A **decorator** is a line starting with `@`, written directly above a `def`. It
  wraps the function with extra behaviour.
- `@require_GET` (already imported) lets only `GET` requests through. Anything else
  gets a **405 Method Not Allowed** response, and your function isn't even run.
  Here's its sister `@require_POST` on a different view:

```python
from django.http import HttpResponse
from django.test import RequestFactory
from django.views.decorators.http import require_POST

@require_POST
def ping(request):
    return HttpResponse("pong")

factory = RequestFactory()
print(ping(factory.post("/ping/")).status_code)   # 200
print(ping(factory.get("/ping/")).status_code)    # 405
```

You'll also see `Method Not Allowed (GET): /ping/` in the Console. That's Django
logging the refused request, the same kind of log line you're about to write.

**Try it:** paste any example from this section into the editor, highlight it and press
**Shift+Enter**. The result appears in the Console tab.

## Step by step

1. **Allow only `GET`.** Put `@require_GET` on the line directly above
   `def health(request):`. **→ test 6**
2. **Really check the database.** Inside a `try:` block, open a cursor with
   `with connection.cursor() as cursor:` and run `cursor.execute("SELECT 1")`.
3. **Handle the failure.** Add `except DatabaseError:`. Inside it:

    - call `logger.exception(...)` with a short message of your own, like
      `"Health check failed: database unavailable"` **→ test 4**
    - return a `JsonResponse` with `{"status": "error", "checks": {"database": "error"}}`
      and `status=503`. Write this dictionary yourself; don't put the error's
      message in it. **→ tests 2, 3 and 5**

4. **Handle success.** After the `try` / `except`, replace the starter's `return`
   with a `JsonResponse` of `{"status": "ok", "checks": {"database": "ok"}}`. It
   uses the default status, 200. **→ test 1**

The shape of steps 2-4 is the same as the `int("ten")` example above: risky work in
`try`, log and give a safe answer in `except`, and carry on normally otherwise.

## Common mistakes

- Returning `{"status": "ok", ...}` without running a query. Test 2 notices,
  because the fake broken database never gets asked.
- Calling `connection.cursor()` outside the `try`. The error then escapes and the
  test crashes instead of getting a 503.
- Importing `connection` again **inside** the function. Your code then uses the
  real database, not the tests' broken one, and tests 2-5 fail. Use the one imported
  at the top.
- `logger.error(...)` instead of `logger.exception(...)`: no traceback, so test 4
  fails.
- Putting `str(error)` or the exception into the response. It contains
  `password=hunter2`, so test 5 fails, and in real life you'd leak a password.
- Forgetting `@require_GET`, or writing it inside the function instead of above it.

## Why it matters

Every real deployment platform (Kubernetes, Render, Railway, AWS load balancers)
lets you set a health check URL and acts on its status code. And good logging is
how you fix production problems you can't reproduce on your laptop: when something
breaks at 3 a.m., the log line with its traceback is often the only clue you have.
