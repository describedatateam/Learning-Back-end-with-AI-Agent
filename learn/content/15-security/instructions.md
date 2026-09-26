# Security essentials

## The big idea

A backend is open to the whole internet, so some of the people sending requests
are **attackers**: people who try to trick your code into doing something it
shouldn't. Most successful attacks don't use clever magic. They use small, ordinary
mistakes that are easy to make and easy to fix, once you know about them.

In this exercise you fix four of those mistakes. Each one is a single small
function, and each defends against a real, common attack. Think of it like the
locks on a house: none of them is complicated, but you need one on every door.

As with data cleaning, the rule behind all four is the same: **never trust what
comes in from outside**. A value a user typed is data to check, never an
instruction to follow.

## New words

| word | meaning |
|---|---|
| **attacker** | Someone who sends requests on purpose to break or misuse your app. |
| **redirect** | A response that says "go to this other address instead". The browser follows it automatically. |
| **`?next=`** | A query value that says where to send the user after logging in, like `/login?next=/tasks/`. |
| **host** | The website part of an address, like `backendlab.test` in `https://backendlab.test/account/`. |
| **relative path** | An address with no host, like `/dashboard/`. It always stays on the current site. |
| **API key** | A long secret password that a program (not a person) sends to prove who it is. |
| **log** | A text file where your app writes down what happened, for developers to read later. |
| **personal data** | Anything that identifies a real person, like an email address. |
| **SQL** | The language databases understand, like `SELECT id FROM sandbox_task WHERE title = 'Deploy'`. |
| **parameterised query** | SQL with a placeholder (`%s`) where the value goes, and the value passed **separately**. |

## The four attacks, as short stories

### 1. Open redirect

Your login page sends people to `?next=` after they log in. An attacker emails your
users a link: `https://backendlab.test/login?next=https://backendlab-login.evil.example`.
The link starts with your real site, so Ada trusts it and logs in. Your site then
**redirects her to the attacker's copy of your site**, which says "Session expired,
please type your password again". She does, and the attacker has her password.

**Fix:** only redirect to your own site. Anything else goes to `/` (the home page).

### 2. Timing attack

Imagine a guard who checks a password one letter at a time and says "wrong!" the
moment a letter doesn't match. A wrong first letter gets a very quick "wrong!"; a
right first letter gets a slightly slower one. By timing the answers very carefully,
an attacker can guess the secret **one letter at a time**. Python's `==` on strings
can behave like that guard.

**Fix:** compare secrets with `hmac.compare_digest`, which always takes the same
time, wherever the strings differ.

### 3. Personal data in logs

Your app logs "Password reset for ada.lovelace@example.com". Logs get copied into
monitoring tools, emailed around while fixing bugs, and kept for months. One day a
log file leaks, and now thousands of customers' emails are public, which in many
countries is also against the law.

**Fix:** mask the data before logging it: `a***@example.com` is still useful for
debugging, but doesn't expose the person.

### 4. SQL injection

A search box looks tasks up by title, and the code glues the typed text straight
into SQL. Someone types `x' OR '1'='1` into the box. The quote `'` ends the title
early, and the rest becomes **part of the SQL command**: "title is x, OR 1 equals 1".
Since 1 always equals 1, the query returns **every task of every user**. With other
typed text, an attacker could even delete tables.

**Fix:** never build SQL by gluing strings together. Pass the value separately, so
the database treats it as plain data.

## What your code receives and returns

**The tests call your four functions and pass the values in.** Here are the real
inputs, copied from the tests. `HOSTS` is `["backendlab.test"]`.

**`safe_next_url(url, allowed_hosts)`** (tests 1-2)

| call | must return |
|---|---|
| `safe_next_url("/dashboard/", HOSTS)` | `"/dashboard/"` (unchanged) |
| `safe_next_url("/tasks/?page=2", HOSTS)` | `"/tasks/?page=2"` |
| `safe_next_url("https://backendlab.test/account/", HOSTS)` | `"https://backendlab.test/account/"` |
| `safe_next_url("https://evil.example/login", HOSTS)` | `"/"` |
| `safe_next_url("//evil.example", HOSTS)` | `"/"` (`//` means "another site" to a browser) |
| `safe_next_url("javascript:alert(1)", HOSTS)` | `"/"` (would run code in the browser) |
| `safe_next_url("http://backendlab.test.evil.example/", HOSTS)` | `"/"` (starts like ours, but it's a different host) |
| `safe_next_url("", HOSTS)` and `safe_next_url(None, HOSTS)` | `"/"` |

**`api_key_matches(provided, expected)`** (tests 3-5)

| call | must return |
|---|---|
| `api_key_matches("sk_live_abc123", "sk_live_abc123")` | `True` |
| `api_key_matches("sk_live_abc124", "sk_live_abc123")` | `False` |
| `api_key_matches("", "")` and `api_key_matches(None, None)` | `False` (empty keys never match, not even each other) |
| `api_key_matches(None, "secret")` and `api_key_matches("secret", "")` | `False` |

Test 5 also checks that your function really calls `hmac.compare_digest(...)`.

**`mask_email(email)`** (tests 6-7)

| call | must return |
|---|---|
| `mask_email("ada.lovelace@example.com")` | `"a***@example.com"` |
| `mask_email("b@x.io")` | `"b***@x.io"` |
| `mask_email("not-an-email")`, `mask_email("")`, `mask_email(None)`, `mask_email("@example.com")` | `"***"` |

**`find_tasks_by_title(title)`** (tests 8-10). The tests first create two tasks,
`"Deploy"` and `"Secret task"`, then:

| call | must return |
|---|---|
| `find_tasks_by_title("Deploy")` | a list with the Deploy task's id, like `[1]` |
| `find_tasks_by_title("x' OR '1'='1")` | `[]` (nothing is called that) |
| `find_tasks_by_title("Ada's task")` (after creating that task) | a list with its id |

> The starter code runs, but every function is unsafe on purpose. For example the
> starter's `safe_next_url` returns any address it gets, attacker's sites included.

## Tools you'll use

### `url_has_allowed_host_and_scheme(url, allowed_hosts=...)`

- Django's own "is this address safe to redirect to?" check. It's a **function**
  (already imported at the top of your file) that gives back `True` or `False`.
- Pass the address first and the allowed hosts second. Writing `allowed_hosts=`
  makes the call easier to read. A list or a set of hosts both work.
- It already rejects other hosts, `//...`, `javascript:...`, and empty or missing
  addresses.

```python
from django.utils.http import url_has_allowed_host_and_scheme

for url in ["/cart/", "https://shop.test/cart/", "https://evil.example/", "//evil.example"]:
    print(url, url_has_allowed_host_and_scheme(url, allowed_hosts=["shop.test"]))
# /cart/ True
# https://shop.test/cart/ True
# https://evil.example/ False
# //evil.example False
```

- Common mistake: writing your own check like `url.startswith("/")`. It lets
  `//evil.example` through, because that starts with `/` too.

### `not value`: catching empty and missing at once

- `not ""` and `not None` are both `True`, so `if not value:` catches both "empty"
  and "missing" in one check.

```python
for value in ["", None, "abc"]:
    print(repr(value), not value)
# '' True
# None True
# 'abc' False
```

### `hmac.compare_digest(a, b)`

- Compares two values in **constant time** (always the same speed) and gives back
  `True` or `False`.
- It's a function inside the `hmac` module, which your file already imports, so call
  it as `hmac.compare_digest(...)`.
- Turn strings into **bytes** first with `.encode()`. Plain strings only work if they
  contain no accented or special letters (`"café"` would crash).

```python
import hmac

print(hmac.compare_digest("tea".encode(), "tea".encode()))   # True
print(hmac.compare_digest("tea".encode(), "tee".encode()))   # False
```

- Common mistake: calling `.encode()` on `None` crashes. Check for empty or missing
  values **before** comparing.

### `text.partition("@")` and `text[0]`

- You met `partition` in exercise 1: it splits at the first separator and gives
  back 3 pieces. If the separator isn't there, the last two pieces are empty.
- `text[0]` is the first character of a string.

```python
print("tea@shop.test".partition("@"))   # ('tea', '@', 'shop.test')
print("no-at-sign".partition("@"))      # ('no-at-sign', '', '')
print("@shop.test".partition("@"))      # ('', '@', 'shop.test')
print("tea"[0])                         # t
```

- `partition` crashes on `None`. A handy trick: `(value or "")` gives `""` when
  `value` is `None`, and the value itself otherwise.

### `cursor.execute(sql, [values])`: a parameterised query

- `connection.cursor()` lets you send raw SQL to the database. `cursor.execute(...)`
  takes the SQL as the **first** argument, and a **list** of values as the second.
- In the SQL, write `%s` (no quotes around it!) wherever a value goes. The database
  driver puts the value in safely, so quotes inside it are just letters.

```python
from django.db import connection
from sandbox.models import Task

pen = Task.objects.create(title="Buy pens")
with connection.cursor() as cursor:
    cursor.execute("SELECT title FROM sandbox_task WHERE id = %s", [pen.id])
    print(cursor.fetchall())   # [('Buy pens',)]
```

- Common mistake: `"... WHERE title = '%s'"` with quotes around `%s`, or
  `"..." % title`. Both glue the value into the text again. The value must go in
  the separate list.

### See the injection happen

The starter's `find_tasks_by_title` builds its SQL with an f-string. This shows what
the database actually receives:

```python
title = "x' OR '1'='1"
print(f"SELECT id FROM sandbox_task WHERE title = '{title}'")
# SELECT id FROM sandbox_task WHERE title = 'x' OR '1'='1'
```

And this runs your own `find_tasks_by_title` against a small test database:

```python
from sandbox.models import Task

Task.objects.create(title="Deploy")
Task.objects.create(title="Secret task")
print(find_tasks_by_title("x' OR '1'='1"))
# With the starter code: [1, 2]  <- every row!
# After your fix:        []
```

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The result appears in the Console tab.

## Step by step

The step numbers match the `TODO` numbers in your file.

### `safe_next_url(url, allowed_hosts)`

**Step 1.** If `url` is not empty and `url_has_allowed_host_and_scheme(...)` says
it's safe, return `url` unchanged. Pass `allowed_hosts=allowed_hosts`.
**→ test 1**

**Step 2.** Otherwise return `"/"`. **→ test 2**

### `api_key_matches(provided, expected)`

**Step 3.** If either key is empty or `None`, return `False` straight away. Use
`if not provided or not expected:`. **→ test 4**

**Step 4.** Otherwise return the result of `hmac.compare_digest(...)` on the two
keys, each turned into bytes with `.encode()`. **→ tests 3 and 5**

### `mask_email(email)`

**Step 5.** Split the email at the `@` with `partition`, using `(email or "")` so
`None` doesn't crash: `local, at, domain = ...`.

**Step 6.** If any of the three pieces is empty, return `"***"`. An empty `at`
means there was no `@`; an empty `local` means the email started with `@`.
**→ test 7**

**Step 7.** Otherwise build the masked email with an f-string: the first character
of `local`, then `***@`, then the domain. **→ test 6**

### `find_tasks_by_title(title)`

**Step 8.** Change only the `cursor.execute(...)` line. Keep the same `SELECT`,
but replace `'{title}'` with a bare `%s`, turn the f-string into a normal string,
and pass `[title]` as the second argument. Keep the `return` line as it is.
**→ tests 8, 9 and 10**

Test 10 shows why this matters even without an attacker: with the f-string, the
quote in `Ada's task` breaks the SQL and the query crashes.

## Common mistakes

- `url.startswith("/")` as the redirect check: `//evil.example` sneaks through.
- Returning the result of `url_has_allowed_host_and_scheme(...)` itself. It gives
  `True` or `False`, but `safe_next_url` must return an **address**: `url` or `"/"`.
- Using `provided == expected` for the keys: tests 3-4 may pass, but test 5 checks
  for `hmac.compare_digest`. Also, `"" == ""` is `True`, which test 4 forbids.
- `email.split("@")` crashes on `None` and gives the wrong number of pieces for
  `"not-an-email"`. `partition` always gives exactly three.
- Putting quotes around the placeholder (`'%s'`) or using `%` / an f-string to fill
  it in. The value must travel in the separate list: `[title]`.

## Why it matters

These four mistakes are in every list of common web security bugs. Django already
protects you in many places: the ORM (`Task.objects.filter(title=title)`) always uses
parameterised queries, and Django's login view checks `?next=` with the same
function you used. Knowing the attacks helps you spot the places where you step
outside that protection yourself.
