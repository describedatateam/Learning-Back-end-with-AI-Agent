# Your first JSON views

## The big idea

In exercise 1 you turned a raw HTTP request into a tidy dictionary. Django does
that job for you. Every time a request arrives, Django reads the raw text, packs
it into a **request object**, and then **calls a function you wrote**, passing that
object in as the first argument. That function is called a **view**.

A view has one job: look at the request and give back a **response**. For an API
the response is usually **JSON**, text that looks almost exactly like a Python
dictionary, so any program (a website, a phone app, a script) can read it.

Think of a view like a clerk at a counter. A form (the request) is handed over,
the clerk checks it, and hands back a reply slip (the response) with a stamp on
top: "OK", "you filled this in wrong" or "wrong counter". That stamp is the
**status code**.

It's also a lot like validating data before analysis: you check that a column
exists and holds numbers before you do maths on it. Here you check what the
client sent before you use it.

## New words

| word | meaning |
|---|---|
| **view** | A Python function that receives a request and returns a response. |
| **request object** | What Django gives your view: the request, already split into parts, like `request.method` and `request.GET`. |
| **response** | What your view gives back: some content plus a status code. |
| **JSON** | A text format for data that looks like a Python dict: `{"message": "Hello"}`. |
| **status code** | A 3-digit number on every response that says how it went. |
| **query parameter** | A value in the address after `?`, like `name=Ada` in `/greet/?name=Ada`. |
| **request body** | Data sent *inside* the request (not in the address), usually with `POST`. |
| **decorator** | A line starting with `@` just above a `def`. It wraps the function with extra behaviour. |

The status codes you need:

| code | name | when to use it |
|---|---|---|
| **200** | OK | Everything worked. This is the default. |
| **400** | Bad Request | The client sent something wrong, like a missing name or broken JSON. |
| **405** | Method Not Allowed | This view doesn't accept that method, like a `POST` to a read-only view. |

Codes starting with **4** mean "the client made a mistake". Codes starting with
**5** mean "the server broke". You never want a user's typo to cause a 500.

## What your code receives and returns

You write two views in `views.py`: `greet(request)` and `add(request)`.

**You don't create `request` yourself. The tests build a fake request and call
your view with it.** They use Django's `RequestFactory`, a tool that makes request
objects without running a real server. These lines are copied from the tests:

```python
factory = RequestFactory()

greet(factory.get("/greet/", {"name": "Ada"}))      # like GET /greet/?name=Ada
add(factory.post("/add/", data='{"a": 2, "b": 3.5}', content_type="application/json"))
```

So inside `greet`, `request` holds a `GET` request whose query has `name` set to
`"Ada"`. Inside `add`, `request` holds a `POST` request whose body is the text
`{"a": 2, "b": 3.5}`.

The tests then check the status code and the JSON in your response:

| the test sends | status | JSON body |
|---|---|---|
| `GET /greet/?name=Ada` | 200 | `{"message": "Hello, Ada!"}` |
| `GET /greet/?name=  Grace  ` | 200 | `{"message": "Hello, Grace!"}` |
| `GET /greet/` (no name) | 400 | `{"error": "name is required"}` |
| `GET /greet/?name=   ` (only spaces) | 400 | `{"error": "name is required"}` |
| `POST /greet/` | 405 | (Django fills this in) |
| `POST /add/` body `{"a": 2, "b": 3.5}` | 200 | `{"result": 5.5}` |
| `POST /add/` body `{not json` | 400 | `{"error": "invalid JSON"}` |
| `POST /add/` body `{"a": 1}` | 400 | `{"error": "a and b must be numbers"}` |
| `POST /add/` body `{"a": "1", "b": 2}` | 400 | `{"error": "a and b must be numbers"}` |
| `POST /add/` body `{"a": null, "b": 2}` | 400 | `{"error": "a and b must be numbers"}` |
| `GET /add/` | 405 | (Django fills this in) |

The error messages must match **exactly**, including the lower-case letters.

> `null` is how JSON writes Python's `None`. When Django reads that body,
> `"a"` becomes `None`.

## Tools you'll use

The top of `views.py` already imports everything below (`json`, `JsonResponse`,
`require_GET`, `require_POST`), so you can use them straight away. The Try-it
examples also import `RequestFactory` so they can make a fake request.

### `request.method` and `request.GET.get(name, default)`

- `request.method` is the method as text: `"GET"` or `"POST"`.
- `request.GET` holds the **query parameters**. It works like a dictionary.
- `.get(name, default)` is a **method** (dot, round brackets). It gives back the
  value, or `default` if the parameter isn't there. The value is always a string.

```python
from django.test import RequestFactory

request = RequestFactory().get("/weather/", {"city": "  Paris  "})
print(request.method)                          # GET
print(request.GET.get("city", ""))             #   Paris   (spaces kept)
print(request.GET.get("country", "unknown"))   # unknown  (missing, so the default)
print(request.GET.get("city", "").strip())     # Paris
```

- Common mistake: `request.GET["city"]` with square brackets crashes when the
  parameter is missing. `.get(...)` with a default never crashes.
- `request.GET` is about the **query**, not the method. A `POST` request can have
  a query too.

### `JsonResponse(data, status=...)`

- Turns a Python dict into a JSON response. It's a **class you call like a
  function**: `JsonResponse({...})`.
- The status code is 200 unless you pass `status=` as a **keyword argument**.

```python
response = JsonResponse({"error": "city is required"}, status=400)
print(response.status_code)   # 400
print(response.content)       # b'{"error": "city is required"}'
print(JsonResponse({"temp": 21}).status_code)   # 200
```

The `b'...'` means the content is **bytes**, raw text ready to send over the
network. You don't need to do anything with it.

### Decorators: `@require_GET` and `@require_POST`

- Put the decorator on the line **directly above** `def`. It checks the method
  before your code runs. If the method is wrong, it returns a **405** response
  for you and your function body never runs.

```python
from django.test import RequestFactory

@require_POST
def ping(request):
    return JsonResponse({"pong": True})

print(ping(RequestFactory().post("/ping/")).status_code)   # 200
print(ping(RequestFactory().get("/ping/")).status_code)    # 405
```

The Console also prints a log line, `Method Not Allowed (GET): /ping/`. That's
Django noting the 405, not an error in your code.

- Common mistake: writing `require_GET(greet)` inside the function, or adding
  brackets: `@require_GET()`. Just write `@require_GET` on its own line.

### `request.body` and `json.loads(text)`

- `request.body` is the raw body of the request, as bytes.
- `json.loads(...)` is a **function** from the `json` module. It turns JSON text
  (or bytes) into Python: a JSON object becomes a dict.

```python
from django.test import RequestFactory

request = RequestFactory().post("/order/", data='{"item": "tea", "qty": 2}', content_type="application/json")
print(request.body)        # b'{"item": "tea", "qty": 2}'
data = json.loads(request.body)
print(data)                # {'item': 'tea', 'qty': 2}
print(data["qty"] * 10)    # 20  (a real number now, not text)
print(data.get("price"))   # None  (.get on a missing key gives None)
```

### `try` / `except json.JSONDecodeError`

- If the text isn't valid JSON, `json.loads` **raises an error** and your view
  would crash with a 500. `try` / `except` catches that error so you can reply
  with a polite 400 instead.

```python
try:
    data = json.loads("{oops")
    print("parsed:", data)
except json.JSONDecodeError:
    print("That was not valid JSON")
# prints: That was not valid JSON
```

The code under `try:` runs first. If it raises a `JSONDecodeError`, Python jumps
straight to the `except` block. Returning from inside `except` ends the view there.

### `isinstance(value, (int, float))`

- Asks "is this value one of these types?" and gives back `True` or `False`.
  Passing a **tuple** of types, `(int, float)`, means "any of these".

```python
print(isinstance(3, (int, float)))      # True
print(isinstance(2.5, (int, float)))    # True
print(isinstance("3", (int, float)))    # False  (text, even though it looks like a number)
print(isinstance(None, (int, float)))   # False
```

### f-strings: `f"...{name}..."`

- Put `f` before the quotes and any `{variable}` inside is replaced by its value:
  `f"Hi, {city}!"` with `city = "Paris"` gives `"Hi, Paris!"`.

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The result appears in the Console tab.

## Step by step

### `greet(request)`

1. **Allow only GET.** Put `@require_GET` on the line directly above
   `def greet(request):`. **→ test 4**
2. **Read the name.** Use `request.GET.get("name", "")` so a missing name becomes
   an empty string, then call `.strip()` on it. Store the result in a variable,
   for example `name`. **→ helps tests 2 and 3**
3. **Reject an empty name.** If `name` is empty (`if not name:`), return
   `JsonResponse({"error": "name is required"}, status=400)`. An empty string
   counts as "false" in Python, so `not ""` is `True`. **→ test 3**
4. **Greet.** Otherwise return a `JsonResponse` whose dict has the key `"message"`
   and the text `Hello, <name>!`, built with an f-string. Replace the starter's
   `"Hello, world!"` line. **→ tests 1 and 2**

### `add(request)`

5. **Allow only POST.** Put `@require_POST` directly above `def add(request):`.
   **→ test 8**
6. **Read the JSON body safely.** Inside a `try:`, set
   `data = json.loads(request.body)`. In `except json.JSONDecodeError:`, return
   `{"error": "invalid JSON"}` with status 400. **→ test 6**
7. **Check `a` and `b`.** Get them with `data.get("a")` and `data.get("b")` (a
   missing key gives `None`, no crash). If **either** one is not an `int` or
   `float`, return `{"error": "a and b must be numbers"}` with status 400.
   **→ test 7**
8. **Add them.** Return `{"result": ...}` with the sum. Replace the starter's
   `{"result": 0}` line. **→ test 5**

Here's the same "check, then use" shape on different data, to copy the pattern
from (it's not a view, just the logic):

```python
data = {"width": 4, "height": "tall"}
w, h = data.get("width"), data.get("height")
if not isinstance(w, (int, float)) or not isinstance(h, (int, float)):
    print("width and height must be numbers")
else:
    print(w * h)
# prints: width and height must be numbers
```

## Common mistakes

- Returning the error dict but forgetting `status=400`. The JSON looks right but
  the test sees 200.
- Using `request.POST` for the JSON body. `request.POST` only works for HTML form
  data. For JSON, use `json.loads(request.body)`.
- Checking `if a and b:` to mean "they're numbers". `"1"` is true too, and `0` is
  false. Use `isinstance`.
- Writing `or` vs `and` the wrong way round in the number check. The error is
  needed if `a` is bad **or** `b` is bad.
- A small typo in an error message, like `"Name is required"`. The tests compare
  the text exactly.

## Why it matters

Every Django API endpoint is a view like these: read the request, validate it,
return JSON with the right status code. Later, Django REST Framework does the
JSON parsing and checking for you, but it follows exactly this pattern.
