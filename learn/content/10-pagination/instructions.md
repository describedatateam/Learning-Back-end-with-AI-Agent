# Paginate a list

## The big idea

Imagine an API with 50,000 tasks. If one request sent back **all** of them, the
response would be huge, slow to build and slow to download, and the phone or
browser on the other end would struggle to show it. So APIs send the data in
**pages**: a small slice at a time, plus a few numbers that say where you are.

A client asks for a page with **query parameters** (the extras after `?` that you
met in exercise 1):

```
GET /api/tasks/?page=2&page_size=10
```

and gets back one page of results with some **metadata** (facts about the data):

```python
{
    "count": 42,          # how many items exist in total
    "page": 2,            # which page this is
    "total_pages": 5,     # how many pages there are
    "next_page": 3,       # the page to ask for next (None on the last page)
    "previous_page": 1,   # the page before (None on page 1)
    "results": [...],     # the 10 items on this page
}
```

You already do this in data analysis: `df.head(10)` shows the first 10 rows, and
`df.iloc[10:20]` shows the next 10. Pagination is the same idea, done by the
server, with the client choosing which chunk it wants.

## New words

| word | meaning |
|---|---|
| **pagination** | Splitting a long list into numbered pages and returning one page at a time. |
| **page** | Which chunk the client wants. Page 1 is the first chunk. |
| **page size** | How many items are on one page. |
| **metadata** | Extra facts about the data, like `count` and `total_pages`, sent next to the results. |
| **clamp** | Push a number back inside a limit: if it's too big, use the limit instead. |
| **exception** | An error that stops the code, like `ValueError`. |
| **raise** | Make an exception happen on purpose, to say "this input is wrong". |

## What your code receives and returns

You don't create the list or the numbers yourself. **The tests call your function
and pass them in** as the parameters `items`, `page`, `page_size` and (sometimes)
`max_page_size`. In the tests, `items` is a list of the numbers 1 to 42:

```python
ITEMS = list(range(1, 43))   # [1, 2, 3, ..., 42]  -> 42 items
```

A test calls `paginate(ITEMS, page=1, page_size=10)` and checks it returns:

```python
{
    "count": 42,
    "page": 1,
    "total_pages": 5,
    "next_page": 2,
    "previous_page": None,
    "results": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
}
```

Other calls from the tests, and what they expect:

| call | expected |
|---|---|
| `paginate(ITEMS, page=3, page_size=10)` | `results` is `[21, ..., 30]`, `page` 3, `previous_page` 2, `next_page` 4 |
| `paginate(ITEMS, page=5, page_size=10)` | `results` is `[41, 42]` (the last page is shorter), `next_page` is `None` |
| `paginate(ITEMS, page="2", page_size="20")` | `page` is the **number** `2`, `results` is `[21, ..., 40]` |
| `paginate(ITEMS, page="abc", page_size=10)` | raises `ValueError` |
| `paginate(ITEMS, page=6, page_size=10)` | raises `ValueError("Invalid page.")` |
| `paginate(list(range(200)), page=1, page_size=1000, max_page_size=50)` | 50 results, `total_pages` 4 |
| `paginate([], page=1)` | `count` 0, `total_pages` 1, `results` `[]`, both neighbours `None` |

> Why can `page` be a string like `"2"`? Because everything in a web address is
> text. When a client writes `?page=2`, the server receives the **string** `"2"`,
> not the number `2`. Your function must turn it into a number before using it.

> `items`, `page` and `page_size` only exist **inside** your function while a
> test is calling it. To experiment in the Console, make your own sample list
> first (see "Try it" below).

## Tools you'll use

### `int(value)`

- Turns a string (or a number) into a whole number. It's a **function**, so you
  pass the value in brackets.

```python
int("7")       # 7
int(" 12 ")    # 12  (spaces around it are fine)
int("seven")   # ValueError: invalid literal for int() with base 10: 'seven'
int(None)      # TypeError: int() argument must be a string, ... not 'NoneType'
```

- Common mistake: bad text gives a `ValueError`, but `None` gives a **different**
  error, a `TypeError`. The tests pass `None` too, so you need to handle both.

### `try` / `except`

- Runs some code, and if a certain error happens, runs a backup block instead of
  crashing. Put several error types in brackets to catch any of them.

### `raise ValueError("message")`

- Stops the function straight away with an error you choose. This is how a
  function says "you gave me bad input". The code that called it (here, the
  tests) sees the error.

Here are both together, checking an age typed into a form (different data from
the exercise):

```python
def check_age(value):
    try:
        age = int(value)
    except (TypeError, ValueError):
        raise ValueError("age must be a whole number")
    if age < 0:
        raise ValueError("age cannot be negative")
    return age

check_age("30")    # 30
check_age("old")   # ValueError: age must be a whole number
check_age("-4")    # ValueError: age cannot be negative
```

### `min(a, b)` and `max(a, b)`

- Give back the smaller / bigger of the values.

```python
min(80, 25)   # 25   -> "no more than 25"
max(1, 0)     # 1    -> "at least 1"
```

- `min(asked_for, limit)` is the usual way to **clamp** a number: you get what
  was asked for, but never more than the limit.

### `math.ceil(number)`

- Rounds **up** to the next whole number. `math` is already imported at the top
  of your file, so call it as `math.ceil(...)`.

```python
import math

23 / 5              # 4.6
math.ceil(23 / 5)   # 5   -> 23 songs, 5 per page, need 5 pages
math.ceil(20 / 5)   # 4   -> exactly 4 full pages
```

### Slicing: `my_list[start:stop]`

- Gives back the items from position `start` up to, **but not including**,
  position `stop`. Positions count from 0. Square brackets, with a colon.

```python
songs = ["s1", "s2", "s3", "s4", "s5", "s6", "s7"]
songs[0:3]     # ["s1", "s2", "s3"]   <- page 1, 3 per page
songs[3:6]     # ["s4", "s5", "s6"]   <- page 2
songs[6:9]     # ["s7"]               <- page 3: past the end is fine, it's just shorter
```

- The start of any page is `(page - 1) * page_size`. For page 2 with 3 per page
  that's `(2 - 1) * 3 = 3`, and `songs[3:3 + 3]` is page 2.

### `value_if_true if condition else value_if_false`

- A one-line `if` that picks between two values.

```python
n = 12
"big" if n > 10 else "small"   # "big"
```

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The Console tab shows the value of the **last** line you
highlighted, so to see one particular line, highlight the lines it needs (like
`import math` or `songs = [...]`) plus that line. When an example raises an error,
the Console shows the error: that's what you want to see.

## Step by step

1. **Turn `page` into a number and check it.** Use `int(page)` inside a
   `try` / `except (TypeError, ValueError)`, and in the `except` block
   `raise ValueError(...)` with a message of your choice. Then, if the number is
   less than 1, `raise ValueError(...)` too. Store the number back in `page`.
   **→ test 5 (the page cases)**
2. **Do the same for `page_size`.** Same checks, same kind of error.
   **→ tests 4 and 5**
   (Tip: steps 1 and 2 are the same code twice. You can write it once as a small
   helper function above `paginate`, like `check_age` in the example, and call it
   for each value.)
3. **Clamp the page size**: `page_size = min(page_size, max_page_size)`.
   **→ test 6**
4. **Work out the totals.** `count` is `len(items)`. `total_pages` is
   `count / page_size` rounded **up**, but never less than 1, so wrap it:
   `max(1, math.ceil(...))`. An empty list then still has one (empty) page.
   **→ test 1, and test 8** (the starter already passes test 8; keep it passing)
5. **Reject a page past the end.** If `page > total_pages`,
   `raise ValueError("Invalid page.")`. Use exactly that message, with the full
   stop. **→ test 7**
6. **Cut out this page's items.** Work out `start = (page - 1) * page_size`,
   then slice `items[start:start + page_size]`. **→ tests 1, 2 and 3**
7. **Work out the neighbours.** `next_page` is `page + 1` if `page` is less than
   `total_pages`, otherwise `None`. `previous_page` is `page - 1` if `page` is
   more than 1, otherwise `None`. **→ tests 1, 2, 3 and 8**
8. **Return one dictionary** with the keys `count`, `page`, `total_pages`,
   `next_page`, `previous_page` and `results`. Make sure `page` is the number
   from step 1, not the original string. **→ all of tests 1-8**

## Common mistakes

- Catching only `ValueError`: `int(None)` raises a `TypeError`, so the `(None, 10)`
  case in test 5 crashes instead of raising `ValueError`.
- Returning the original `page` in the dictionary. For `page="2"` the test wants
  the number `2`, not the string `"2"`.
- Off-by-one slicing: page 1 starts at position **0**, so use `(page - 1) * page_size`,
  not `page * page_size`.
- Using `count // page_size` (rounds **down**): 42 items at 10 per page would give 4
  pages and lose items 41 and 42. Use `math.ceil`.
- Working out `total_pages` **before** clamping `page_size`. For test 6 that uses
  1000 per page and gives 1 page instead of 4. Clamp first (step 3), then count.

## Why it matters

DRF does this for you with `PageNumberPagination`: set a page size in settings and
every list endpoint returns `count`, `next`, `previous` and `results`, and a page
past the end becomes a `404` with `"Invalid page."`. This project uses it in
`core/pagination.py`, with `page_size = 10` and `max_page_size = 50`, the same
numbers as your function's defaults. Now you know what it's doing underneath.
