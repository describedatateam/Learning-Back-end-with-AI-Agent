# Configuration from the environment

## The big idea

The same Django code runs in several places: on your laptop, on a test server and
on the real server that customers use (called **production**). Each place needs
different **settings**: a different database password, a different secret key,
and `DEBUG` switched on at home but **off** in production.

If you wrote those values into `settings.py`, you would have to change the code for
every place, and your secret passwords would end up in git, where anyone who can
read the code can read them. So instead, each computer keeps its own settings in
**environment variables**, and the code just reads them.

An everyday picture: the code is a recipe, and environment variables are the oven
dial in each kitchen. The recipe says "bake at the oven's setting", and each kitchen
sets its own dial.

There's one big catch. Environment variables are **always text**. `DEBUG=False`
gives your program the string `"False"`, not the boolean `False`. And in Python,
every non-empty string counts as true, so `if "False":` runs! If you've cleaned
data, this is the same problem as a CSV column where numbers and yes/no values
arrive as text: you must convert them to proper types before you use them. In this
exercise you write four small helpers that do exactly that.

## New words

| word | meaning |
|---|---|
| **environment variable** | A `NAME=value` setting that lives outside your code, on the computer (or in a `.env` file) that runs it. |
| **setting** | A value that changes how the app behaves, like `DEBUG` or the database password. |
| **production** | The real server that real users use. Mistakes here hurt. |
| **`os.environ`** | Python's view of all environment variables. It works like a dictionary of strings. |
| **truthy** | A value that `if` treats as true. Every non-empty string is truthy, even `"False"` and `"0"`. |
| **default** | The value to use when the variable isn't set. |
| **`ImproperlyConfigured`** | Django's error for "the settings are wrong". You raise it to stop the app with a clear message. |
| **raise** | Stop the function right away with an error, instead of returning a value. |

You can see real examples in this project: open `.env.example`. It contains lines
like `DJANGO_DEBUG=True` and `DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost`, and
`config/settings.py` reads them with `os.environ.get(...)`.

## What your code receives and returns

You don't set the variables yourself. **The tests set an environment variable for a
moment, call your function with the variable's name, and check what comes back.**
So `name` is a string such as `"APP_DEBUG"`, and your function must look up that
name in `os.environ`.

Here are real calls from the tests, with the value the variable holds and the
result the tests expect:

**`env_str`** (tests 1-2)

| the variable holds | the test calls | and expects |
|---|---|---|
| `"  backend-lab "` | `env_str("APP_NAME")` | `"backend-lab"` |
| not set | `env_str("APP_NAME", "fallback")` | `"fallback"` |
| `"   "` (only spaces) | `env_str("APP_NAME", "fallback")` | `"fallback"` |
| not set | `env_str("APP_NAME")` | an `ImproperlyConfigured` error whose message contains `APP_NAME` |

**`env_bool`** (tests 3-5)

| the variable holds | the test calls | and expects |
|---|---|---|
| `"1"`, `"true"`, `"True"`, `" YES "` or `"on"` | `env_bool("APP_DEBUG")` | `True` |
| `"0"`, `"false"`, `"False"`, `"no"` or `" OFF "` | `env_bool("APP_DEBUG", default=True)` | `False` |
| not set | `env_bool("APP_DEBUG")` | `False` |
| not set | `env_bool("APP_DEBUG", default=True)` | `True` |
| `"maybe"` | `env_bool("APP_DEBUG")` | an `ImproperlyConfigured` error |

**`env_int`** (test 6)

| the variable holds | the test calls | and expects |
|---|---|---|
| `" 8000 "` | `env_int("APP_PORT", 80)` | `8000` (a number, not the text `"8000"`) |
| not set | `env_int("APP_PORT", 80)` | `80` |
| `"eighty"` | `env_int("APP_PORT", 80)` | an `ImproperlyConfigured` error |

**`env_list`** (tests 7-8)

| the variable holds | the test calls | and expects |
|---|---|---|
| `" localhost, 127.0.0.1 ,,example.com, "` | `env_list("APP_HOSTS")` | `["localhost", "127.0.0.1", "example.com"]` |
| not set | `env_list("APP_HOSTS")` | `[]` |
| not set | `env_list("APP_HOSTS", ["localhost"])` | `["localhost"]` |

Notice the pattern: in every helper, a variable that is **not set** and one that is
**only spaces** are treated the same way: "use the default".

> The starter code runs, but has bugs on purpose. For example, the starter's
> `env_bool` uses `bool(...)` on the text, so `"False"` becomes `True`. Your job is
> to replace each `return` line with correct code.

## Tools you'll use

### `os.environ.get(name)`

- Looks up an environment variable by name. It's a **method** on `os.environ`, so
  you use a dot and round brackets.
- It gives back the value as a **string**, or `None` if the variable isn't set.

```python
import os

os.environ["MY_COLOUR"] = " Blue "      # set one, just for this experiment
print(os.environ.get("MY_COLOUR"))       # " Blue " (the spaces are kept)
print(os.environ.get("NOT_SET_AT_ALL"))  # None
```

- Common mistake: `os.environ["NOT_SET"]` with square brackets crashes with a
  `KeyError` when the variable is missing. `.get(...)` gives `None` instead.

### Why `"False"` is truthy

```python
print(bool("False"))   # True   <- the classic bug
print(bool("0"))       # True
print(bool(""))        # False  (only the empty string is false)
```

So you can't just use `bool(...)`. You have to look at the **words** instead.

### Checking "is it missing or blank?": `is None` and `.strip()`

- `value is None` is `True` when the variable isn't set.
- `"   ".strip()` gives `""`, and `not ""` is `True`. So `not value.strip()` means
  "only spaces (or nothing)".

```python
value = "   "
print(value is None)          # False
print(not value.strip())      # True  -> blank, so use the default
```

- Common mistake: calling `.strip()` on `None` crashes with `AttributeError: 'NoneType'
  object has no attribute 'strip'`. Check `value is None` **first**. Python's `or`
  stops as soon as one side is true, so `value is None or not value.strip()` is safe.

### `word in {...}`: checking against a set of words

- `{"a", "b"}` is a **set**: a bag of values where you only ask "is it in there?".
  `in` gives `True` or `False`.

```python
SIZES = {"small", "medium", "large"}
answer = " Medium "
print(answer.strip().lower() in SIZES)   # True
```

### `raise ImproperlyConfigured("...")`

- Stops the function immediately with an error message. It's already imported at the
  top of your file.
- Use an **f-string** to put the variable's name in the message, so whoever reads it
  knows what to fix.

```python
from django.core.exceptions import ImproperlyConfigured

name = "MY_COLOUR"
raise ImproperlyConfigured(f"Please set {name}.")
# The Console shows: django.core.exceptions.ImproperlyConfigured: Please set MY_COLOUR.
```

- Common mistake: `return ImproperlyConfigured(...)`. That hands the error back as a
  normal value instead of stopping. It must be `raise`.

### `int(text)` with `try` / `except ValueError`

- `int("42")` turns text into a number. `int(" 42 ")` works too (spaces are OK).
- `int("forty")` fails with a `ValueError`. `try` / `except` lets you catch that
  error and do something else, like raising a clearer one.

```python
for text in ["42", "forty"]:
    try:
        print(int(text) + 1)
    except ValueError:
        print(f"{text!r} is not a number")
# 43
# 'forty' is not a number
```

`{text!r}` inside an f-string shows the value with its quotes, which makes spaces
and empty strings visible in error messages.

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The result appears in the Console tab.

## Step by step

All four helpers start the same way, so do that part first.

The step numbers match the `TODO` numbers in your file.

### The shared start: read and clean the value

**Step 1.** Read the variable with `value = os.environ.get(name)`. If
`value is None` or `not value.strip()`, the variable counts as **missing**.
Otherwise, use `value.strip()` from now on.

You need these lines in all four helpers. You can copy them into each one, or
write your own small helper function above `env_str` (for example one that returns
the stripped value, or `None` when it's missing) and call it from all four.

### `env_str(name, default=None)`

**Step 2.** If the value is there, return it stripped. **→ first part of test 1**

**Step 3.** If it's missing: when `default` is not `None`, return `default`
**→ rest of test 1**. When `default` is `None`, it means "this setting is
required", so `raise ImproperlyConfigured(...)` with a message that contains
`name`, for example `f"Set the {name} environment variable."` **→ test 2**

### `env_bool(name, default=False)`

**Step 4.** If it's missing, return `default`. Otherwise make the value
lower-case, then:

- if it's in `{"1", "true", "yes", "on"}`, return `True` **→ test 3**
- if it's in `{"0", "false", "no", "off"}`, return `False` **→ test 4**
- anything else (like `"maybe"`): `raise ImproperlyConfigured(...)` with a message
  naming the variable. **→ test 5**

### `env_int(name, default)`

**Step 5.** If it's missing, return `default`. Otherwise return `int(value)`,
inside a `try`. In the `except ValueError:` part, `raise ImproperlyConfigured(...)`
with a message naming the variable. **→ test 6**

### `env_list(name, default=None)`

**Step 6.** If it's missing, return `default`, or an empty list `[]` if `default`
is `None`. **→ test 8**

**Step 7.** Otherwise split the value at commas, strip each item and skip the
empty ones. Start with an empty list, loop over `value.split(",")`, strip each
piece, and only `.append` it if it isn't empty. **→ test 7**

Here's the same "split, clean and keep the good ones" loop on different data:

```python
raw = " red , ,green,, blue "
colours = []
for piece in raw.split(","):
    piece = piece.strip()
    if piece:                   # "" is falsy, so empty pieces are skipped
        colours.append(piece)
print(colours)   # ['red', 'green', 'blue']
```

If you know list comprehensions, the same thing fits on one line:
`[p.strip() for p in raw.split(",") if p.strip()]`.

## Common mistakes

- Using `bool(value)` or `value == "True"`. The first makes `"False"` true; the
  second makes `"true"` and `"1"` false. Compare the lower-cased word against sets.
- Calling `.strip()` or `.lower()` before checking for `None`. Check `is None` first.
- Forgetting that `"   "` (only spaces) must count as missing, the same as not set.
  That's what the third check in test 1 is about.
- `return ImproperlyConfigured(...)` instead of `raise ImproperlyConfigured(...)`.
- In `env_list`, returning `None` when the variable isn't set. The tests want `[]`.
- In `env_int`, returning the text `"8000"` instead of the number `8000`.

## Why it matters

Real Django projects read `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` and the database
settings from the environment, with helpers just like these (libraries such as
`django-environ` do the same job). Look at the `DEBUG` line in `config/settings.py`:
with your `env_bool` it could simply be `DEBUG = env_bool("DJANGO_DEBUG")`, and a
typo like `DJANGO_DEBUG=ture` would stop the app with a clear error instead of
quietly doing the wrong thing.
