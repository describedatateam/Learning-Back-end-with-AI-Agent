# Consistent error responses

## The big idea

Things go wrong in every API: a client forgets a required field, asks for a task
that doesn't exist, or isn't logged in. When that happens, the server still has to
send back a proper answer: an **HTTP status code** (like `404`) and a JSON body
that says what went wrong.

In Python, "something went wrong" is an **exception**. You've seen them in data
analysis: `df["prise"]` with a typo raises a `KeyError`, and `int("abc")` raises a
`ValueError`. Django REST Framework (DRF) has its own exceptions for web errors,
such as `NotFound` and `ValidationError`. When a view raises one, DRF catches it
and calls an **exception handler**: a function whose only job is to turn the
exception into a response.

The trouble is that DRF's default responses come in **different shapes**. A
frontend developer has to write different code for each one. In this exercise you
write your own exception handler that wraps every error in the **same shape**.
Think of a help desk that takes complaints in any form (a phone call, an email, a
note) and files each one on the same standard form, so whoever reads them later
always knows where to look.

## New words

| word | meaning |
|---|---|
| **exception** | An error object that stops the code, like `KeyError` or `ValueError`. |
| **raise** | Make an exception happen: `raise NotFound()`. |
| **exception handler** | A function that receives an exception and turns it into a response. DRF calls it for you. |
| **status code** | The number at the top of an HTTP response: `400` bad input, `401` not logged in, `403` not allowed, `404` not found, `500` server bug. |
| **`ValidationError`** | The DRF exception for "the data the client sent is wrong", usually one message list per field. |
| **envelope** | A fixed outer shape that every response is wrapped in, like `{"error": {...}}`. |
| **`Response`** | DRF's response object. It has `.status_code` (a number) and `.data` (a dict that becomes the JSON body). |

## What your code receives and returns

You don't create the exceptions yourself. **The tests call your function and pass
an exception in** as the parameter `exc`, plus an empty dict `{}` as `context`
(context normally holds details like which view failed; you only need to pass it
along). For example, test 2 does this:

```python
from rest_framework import exceptions

response = api_exception_handler(exceptions.NotFound(), {})
```

Here's what DRF's own handler gives back for the exceptions in the tests. This is
the **default**, before your changes:

| exception passed in as `exc` | `response.status_code` | `response.data` (the JSON body) |
|---|---|---|
| `exceptions.ValidationError({"title": ["This field is required."]})` | `400` | `{"title": ["This field is required."]}` |
| `exceptions.NotFound()` | `404` | `{"detail": "Not found."}` |
| `exceptions.NotAuthenticated()` | `401` | `{"detail": "Authentication credentials were not provided."}` |
| Django's `PermissionDenied()` | `403` | `{"detail": "You do not have permission to perform this action."}` |
| `KeyError("boom")` (not a web error) | no response: the handler returns `None` | |

Notice the two shapes: validation errors are keyed by **field name**, everything
else has a single `"detail"` key. Your handler must turn **every** one of them into
this shape, keeping the same status code:

```python
# test 1: exceptions.ValidationError({"title": ["This field is required."]})
{"error": {
    "status": 400,
    "message": "Invalid input.",
    "details": {"title": ["This field is required."]},
}}

# test 2: exceptions.NotFound()
{"error": {"status": 404, "message": "Not found.", "details": {}}}
```

The tests also check that:

- `NotAuthenticated()` gives `status` 401 and `message`
  `"Authentication credentials were not provided."` (test 3);
- Django's own `Http404()` and `PermissionDenied()` give `status` 404 and 403
  (test 4);
- for `MethodNotAllowed("POST")`, `Throttled(wait=5)` and `ParseError()`, the
  `status` inside the body equals `response.status_code` (test 5);
- `KeyError("boom")` makes your function return `None` (test 6).

> `exc` and `response` only exist **inside** your function while a test is calling
> it. To experiment in the Console, make your own exception first (see "Try it").

## Tools you'll use

### `exception_handler(exc, context)`

- DRF's built-in handler. It's already imported at the top of your file, and the
  first line of your function already calls it.
- For a DRF or Django web error it gives back a `Response`. For anything else (a
  bug like `KeyError`) it gives back `None`.

```python
from rest_framework import exceptions
from rest_framework.views import exception_handler

response = exception_handler(exceptions.PermissionDenied(), {})
print(response.status_code)   # 403
print(response.data)          # {'detail': ErrorDetail(string='You do not have permission to perform this action.', code='permission_denied')}

print(exception_handler(KeyError("oops"), {}))   # None
```

- `ErrorDetail(string=..., code=...)` is DRF's special kind of string that also
  remembers an error code. It behaves like normal text.

### `.status_code` and `.data`

- These are **attributes** of the response, so you read them with a dot:
  `response.status_code`, not `response["status_code"]`.
- `response.data` is a normal dictionary, so inside it you use square brackets:
  `response.data["detail"]`.
- You can also **replace** `.data` completely: `response.data = {"any": "dict"}`.
  The status code and headers stay the same.

### `str(value)`

- Turns a value into plain text. Use it to turn an `ErrorDetail` into an ordinary
  string.

```python
from rest_framework import exceptions
from rest_framework.views import exception_handler

response = exception_handler(exceptions.ParseError(), {})
str(response.data["detail"])   # 'Malformed request.'
```

### `isinstance(value, SomeClass)`

- Asks "is this value that kind of thing?" and gives `True` or `False`.

```python
from rest_framework import exceptions

print(isinstance(exceptions.ValidationError("bad"), exceptions.ValidationError))   # True
print(isinstance(exceptions.NotFound(), exceptions.ValidationError))               # False
print(isinstance(3, int))                                                         # True
```

- In your file, `ValidationError` is already imported by name, so you can write
  `isinstance(exc, ValidationError)`.

### `if value is None:`

- The usual way to check for "nothing came back". Use `is`, not `==`.

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter** to see the result in the Console. (The Console shows what you
`print`, plus the value of the last line.)

## Step by step

1. **Let DRF do the first pass.** Keep the first line,
   `response = exception_handler(exc, context)`. Then, if `response is None`,
   `return None`. That's a bug rather than a web error, and returning `None` lets
   Django turn it into a `500 Server Error`. **→ test 6** (the starter already
   passes it; make sure it still does)
2. **Pick the message and details for a validation error.** If
   `isinstance(exc, ValidationError)`, the message is exactly `"Invalid input."`
   and the details are the original `response.data` (the per-field messages).
   **→ test 1**
3. **Pick the message and details for every other error.** Otherwise, the message
   is `str(response.data["detail"])` and the details are an empty dict `{}`.
   **→ tests 2, 3 and 4**
4. **Replace the body with the envelope.** Set `response.data` to a dict with one
   key, `"error"`, whose value is another dict with the keys `"status"`,
   `"message"` and `"details"`. For `"status"` use `response.status_code`, so it
   always matches the real code. **→ tests 1-5**
5. **Return the same `response` object.** **→ all of tests 1-6**

Here's the same "choose, then wrap" pattern on different data, to copy the shape
from:

```python
order = {"item": "tea", "problem": "out of stock"}

if order["problem"] == "out of stock":
    note, extra = "Sorry, we ran out.", {"item": order["item"]}
else:
    note, extra = order["problem"], {}

reply = {"reply": {"code": 7, "note": note, "extra": extra}}
print(reply)   # {'reply': {'code': 7, 'note': 'Sorry, we ran out.', 'extra': {'item': 'tea'}}}
```

## Common mistakes

- Reading `response.data["detail"]` for a validation error: its body has field
  names instead of `"detail"`, so you get a `KeyError`. Check for
  `ValidationError` **first**.
- Returning your new dict instead of `response`. The tests read
  `response.status_code`, and a dict doesn't have one. Put the dict in
  `response.data` and return `response`.
- Typing the status by hand (like `"status": 400`). Test 5 checks 405, 429 and 400
  errors, so always use `response.status_code`.
- Forgetting the outer `"error"` key, so the body is `{"status": ..., ...}`
  instead of `{"error": {"status": ..., ...}}`.
- Turning `None` into a 400 or 500 response yourself. Unexpected bugs should
  stay 500s (and get logged), not look like the client's fault.

## Why it matters

Every client of your API (a React app, a mobile app, another service) can now
handle errors with one piece of code: read `body["error"]["message"]` and show
it. You switch the handler on for the whole project with one setting, for example
`REST_FRAMEWORK = {"EXCEPTION_HANDLER": "core.exceptions.api_exception_handler"}`.
