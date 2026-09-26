# Read an HTTP request

## The big idea

When you open a website, your browser sends a short **text message** to a server
asking for something, for example "please give me the list of tasks". That message
is an **HTTP request**. A web page usually needs many of them: one for the HTML, and
then more small requests for each image, CSS file and JavaScript file.

A backend's first job is to **read** that message and pull out the useful parts:
what the client wants to do, which address it asked for, and any extra details.

If you've cleaned data before, this will feel familiar. A request arrives as one
messy string, and you split it into tidy, labelled fields, just like turning a raw
text column into separate columns.

## New words

| word | meaning |
|---|---|
| **request** | The text message a client (like a browser) sends to a server. |
| **method** | The verb at the start: `GET` = read something, `POST` = create something. |
| **path** | Which address was asked for, like `/api/tasks/`. |
| **query string** | Optional extras after a `?` in the address, like `?status=done&page=2`. |
| **headers** | `Name: value` lines with extra information, like which website it's for. |
| **head** | The request line plus the headers: everything before the first blank line. |
| **body** | Everything after the first blank line. `GET` requests usually have an empty body. |
| **parameter** | The name a function gives to the value it's called with, like `raw` in `def parse_request(raw):`. |

## What your code receives and returns

You don't type the request yourself. **The tests call your function and pass the
request in as the parameter `raw`.** Inside `parse_request`, `raw` holds a string like
this one, which is copied from the tests:

```python
raw = (
    "GET /api/tasks/?status=done&page=2 HTTP/1.1\r\n"
    "Host: localhost:8000\r\n"
    "Accept:   application/json  \r\n"
    "\r\n"
)
```

`\r\n` is how HTTP ends each line (it means "new line"), and the `\r\n\r\n` at the
end is the **blank line** that separates the head from the body.

The tests then check that `parse_request(raw)` returns exactly this dictionary:

```python
{
    "method": "GET",
    "path": "/api/tasks/",
    "query": {"status": "done", "page": "2"},
    "version": "HTTP/1.1",
    "headers": {"host": "localhost:8000", "accept": "application/json"},
    "body": "",
}
```

They also call `is_safe_method("GET")`, `is_safe_method("post")` and so on, and
check for `True` or `False`.

> Because `raw` is a parameter, it only exists **inside** your function while a
> test is calling it. To experiment in the Console, make your own sample string
> first (see "Try it" below).

## Tools you'll use

### `text.partition(separator)`

- Splits a string at the **first** place the separator appears, and gives back
  3 pieces: before, the separator itself, after.
- It's a **method**, so you call it on a string with a dot: `text.partition(...)`.

```python
before, sep, after = "name: Ada Lovelace".partition(": ")
print(before)   # name
print(sep)      # ": " (the separator itself)
print(after)    # Ada Lovelace
```

- It only splits once, which is exactly what you want for `"Host: localhost:8000"`:
  only the first colon counts.

### Unpacking: `a, b, c = ...`

- When something gives back several values, you can store each one in its own
  variable in one line. The number of names on the left must match.
- Use `_` for a piece you don't need: `before, _, after = text.partition(":")`.

```python
first, last = "Ada Lovelace".split(" ")
print(first)   # Ada
print(last)    # Lovelace
```

### `text.split(separator)`

- Cuts a string at **every** separator and gives back a list.

```python
print("red,green,blue".split(","))          # ['red', 'green', 'blue']
print("one\r\ntwo\r\nthree".split("\r\n"))   # ['one', 'two', 'three']
```

### `urlsplit(address)`

- Breaks a web address into named parts. It's a **function** (imported at the top of
  your file), so you pass the text in brackets: `urlsplit(text)`, **not** `text.urlsplit()`.
- The result has **attributes**, which you read with a dot: `.path` and `.query`.
  It's not a dictionary, so `parts["path"]` doesn't work.

```python
from urllib.parse import urlsplit

parts = urlsplit("/shop/search/?item=tea&size=large")
print(parts.path)    # /shop/search/
print(parts.query)   # item=tea&size=large
```

### `parse_qsl(query)` and `dict(...)`

- `parse_qsl` turns a query string into a **list of pairs**. `dict(...)` turns a list
  of pairs into a dictionary.

```python
from urllib.parse import parse_qsl

pairs = parse_qsl("item=tea&size=large")
print(pairs)                  # [('item', 'tea'), ('size', 'large')]
print(dict(pairs))            # {'item': 'tea', 'size': 'large'}
print(dict(parse_qsl("")))    # {}  (an empty query gives an empty dict)
```

### `.lower()`, `.upper()` and `.strip()`

- `.lower()` / `.upper()` give back a copy of the text in lower / upper case.
- `.strip()` removes spaces from both ends.
- You can chain them: `"  Hello ".strip().lower()` gives `"hello"`.

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The Console tab shows everything you `print()`, plus the value
of the last line you highlighted.

## Step by step

### `parse_request(raw)`

1. **Split the head from the body** at the first blank line, `"\r\n\r\n"`, using
   `partition`. Keep the part before (the head) and the part after (the body).
   **→ helps test 7**
2. **Split the head into lines** with `.split("\r\n")`. The first line is the
   request line and the rest are header lines. (`first, *rest = some_list` puts
   the first item in `first` and all the others in the list `rest`.)
3. **Split the request line into three words** at the spaces:
   `method, target, version = ...`. **→ test 1**
4. **Split the target into path and query** with `urlsplit(target)`. Use `.path` for
   the path. For the query, pass `.query` to `parse_qsl` and wrap the result in
   `dict(...)`. **→ tests 2, 3 and 4**
5. **Build a headers dictionary.** Start with an empty dict, `headers = {}`. Loop
   over the header lines. For each line, split it at the **first** colon with
   `partition(":")`, make the name lower-case and strip the value, then store it:
   `headers[name] = value`. **→ tests 5 and 6**
6. **Return one dictionary** with the keys `method`, `path`, `query`, `version`,
   `headers` and `body`. **→ all of tests 1-7**

Here's the same "loop and build a dict" pattern on different data, to copy the
shape from:

```python
lines = ["Fruit : Apple ", "Colour: Red"]
info = {}
for line in lines:
    key, _, value = line.partition(":")
    info[key.strip().lower()] = value.strip()
print(info)   # {'fruit': 'Apple', 'colour': 'Red'}
```

### `is_safe_method(method)`

Some requests only **read** data (`GET`, `HEAD`, `OPTIONS`); others **change** it
(`POST`, `PUT`, `PATCH`, `DELETE`). Servers use a check like this to decide, for
example, whether a visitor who isn't logged in may do something: reading is often
allowed, changing is not.

7. Return `True` if the method is `GET`, `HEAD` or `OPTIONS`, in **any** capitalisation
   (`"get"`, `"Get"`, `"GET"`), and `False` otherwise. Turn the method into upper
   case first, then check whether it's in a set of the safe ones:
   `"GET" in {"GET", "HEAD"}` gives `True`. **→ tests 8 and 9**

## Common mistakes

- `raw.urlsplit(...)`: `urlsplit` is a function, so write `urlsplit(something)`.
- `parts["path"]`: the result of `urlsplit` uses dots, `parts.path`.
- Splitting headers with `.split(":")` breaks `Host: localhost:8000` into three
  pieces. `partition(":")` splits only at the first colon.
- Forgetting `dict(...)` around `parse_qsl(...)` gives a list of pairs, not a dict.
- Running a line that uses `raw` in the Console gives `NameError: name 'raw' is not
  defined`. That's expected: make your own sample string to experiment with.

## Why it matters

Django does all of this for you. Inside a Django view you get `request.method`,
`request.path`, `request.GET` (the query), `request.headers` and `request.body`,
ready to use. Now you know what's underneath them.
