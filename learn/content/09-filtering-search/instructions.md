# Filter, search & order

## The big idea

A list endpoint like `GET /api/tasks/` could send back every task. But users
don't want everything: they want *"my high-priority tasks due before Friday, most
urgent first"*. The client asks for that by adding **query parameters** to the
address:

```
GET /api/tasks/?status=todo&priority=high&due_before=2025-03-01&ordering=due_date
```

The backend reads those parameters and turns them into a database question: which
rows, and in what order. In Django that question is called a **queryset**.

If you've used pandas, you already know the idea. `?status=todo` is like
`df[df["status"] == "todo"]`, `?search=deploy` is like
`df[df["title"].str.contains("deploy", case=False)]`, and `?ordering=-due_date`
is like `df.sort_values("due_date", ascending=False)`. You're writing the backend
half of a filter panel.

## New words

| word | meaning |
|---|---|
| **query parameters** | The `name=value` pairs after the `?` in an address, joined by `&`. |
| **`request.query_params`** | Where DRF puts them, as a dictionary-like object: `{"status": "todo", ...}`. |
| **queryset** | A description of which rows to fetch from a table, and in what order. Django turns it into SQL for you. |
| **filter** | Keep only the rows that match a condition. Several filters together mean "all of these must match" (AND). |
| **lookup** | An extra word after a field name with `__` (two underscores), like `title__icontains` or `due_date__lte`, that changes how it compares. |
| **case-insensitive** | Capital and small letters count as the same: `"DEPLOY"` matches `"Deploy"`. |
| **ordering** | The sort order. `"title"` is A to Z; `"-title"` (with a minus) is Z to A. |
| **whitelist** | A fixed list of allowed values. Anything not on it is ignored. |

## What your code receives and returns

You don't call `filter_tasks` yourself. **The tests call it and pass in two
things**: `queryset`, which is all the tasks (`Task.objects.all()`), and `params`,
a dictionary of query parameters. In a real view, `params` would be
`request.query_params`; the tests use a plain dict, which works the same way.

Before the tests run, they create these four tasks (copied from the tests). The
`Task` model has the fields `title`, `status`, `priority` and `due_date`:

| id | title | status | priority | due_date |
|---|---|---|---|---|
| 1 | Deploy API | todo | high | 2025-03-01 |
| 2 | Write docs | done | low | 2025-02-01 |
| 3 | Fix deploy script | todo | low | *(none)* |
| 4 | Answer email | in_progress | medium | 2025-04-01 |

Your function must **return a queryset**. The tests take the titles from it, in
order, and compare them with the expected list:

| test | `params` | expected titles |
|---|---|---|
| 1 | `{}` | `["Deploy API", "Write docs", "Fix deploy script", "Answer email"]` |
| 2 | `{"status": "todo"}` | `["Deploy API", "Fix deploy script"]` |
| 3 | `{"priority": "low"}` | `["Write docs", "Fix deploy script"]` |
| 4 | `{"status": "todo", "priority": "low"}` | `["Fix deploy script"]` |
| 5 | `{"search": "DEPLOY"}` | `["Deploy API", "Fix deploy script"]` |
| 6 | `{"due_before": "2025-03-01"}` | `["Deploy API", "Write docs"]` |
| 7 | `{"due_before": "next friday"}` | raises `ValueError` |
| 8 | `{"ordering": "title"}` | `["Answer email", "Deploy API", "Fix deploy script", "Write docs"]` |
| 8 | `{"ordering": "-title"}` | `["Write docs", "Fix deploy script", "Deploy API", "Answer email"]` |
| 9 | `{"ordering": "status"}` or `{"ordering": "nonexistent_field"}` | same as test 1 (id order) |
| 10 | `{"status": "", "search": "", "ordering": ""}` | all 4 tasks |

Notice that test 6 keeps a task due **exactly on** 2025-03-01, and leaves out
"Fix deploy script", which has no due date at all.

> The starter just returns the queryset unchanged, so tests 1, 9 and 10 already
> pass: the database happens to hand back tasks in id order. You still need to
> sort by `id` on purpose, so that stays true.

## Tools you'll use

These examples run in the Console, with a practice database and the `Task` model.
The database starts empty on every run, so each example creates its own tasks
(different ones from the tests). `date` is already imported at the top of your file.

### `queryset.filter(field=value)`

- Gives back a **new** queryset with only the matching rows. It doesn't change
  the old one, so store the result: `qs = qs.filter(...)`, just like
  `df = df[...]` in pandas.
- You can chain as many filters as you like; each one narrows the result further.
- `filter` is a **method**, and the condition is written like a keyword argument:
  `field=value`, with `=`, not `==`.

```python
from sandbox.models import Task

Task.objects.create(title="Buy milk", status="done", priority="low", due_date=date(2024, 5, 10))
Task.objects.create(title="Book dentist", status="todo", priority="high", due_date=date(2024, 6, 1))
Task.objects.create(title="Call Milo", status="todo", priority="low")

qs = Task.objects.all()
print(qs)
qs = qs.filter(status="todo")
print(qs)
qs = qs.filter(priority="high")
print(qs)
# <QuerySet [<Task: Buy milk>, <Task: Book dentist>, <Task: Call Milo>]>
# <QuerySet [<Task: Book dentist>, <Task: Call Milo>]>
# <QuerySet [<Task: Book dentist>]>
```

A queryset is **lazy**: building it doesn't touch the database. The query only
runs when the results are used, for example when they're printed or looped over.
That's why chaining filters is cheap.

### Lookups: `__icontains` and `__lte`

- Put a lookup after the field name with **two** underscores.
- `title__icontains="mil"` means "the title contains `mil`, ignoring case".
- `due_date__lte=some_date` means "`due_date` is less than or equal to (on or
  before) that date". Rows with no due date are left out.

```python
from sandbox.models import Task

Task.objects.create(title="Buy milk", status="done", priority="low", due_date=date(2024, 5, 10))
Task.objects.create(title="Book dentist", status="todo", priority="high", due_date=date(2024, 6, 1))
Task.objects.create(title="Call Milo", status="todo", priority="low")

print(Task.objects.filter(title__icontains="MIL"))
print(Task.objects.filter(due_date__lte=date(2024, 5, 31)))
print(Task.objects.order_by("title"))
print(Task.objects.order_by("-title"))
# <QuerySet [<Task: Buy milk>, <Task: Call Milo>]>
# <QuerySet [<Task: Buy milk>]>
# <QuerySet [<Task: Book dentist>, <Task: Buy milk>, <Task: Call Milo>]>
# <QuerySet [<Task: Call Milo>, <Task: Buy milk>, <Task: Book dentist>]>
```

There's also `title__contains` without the `i`. On some databases (like
PostgreSQL) it cares about capital letters, so use `icontains` for search.

### `queryset.order_by("field")`

- Sorts the queryset by a field, given as a string. A `-` in front sorts
  backwards. (See the last two lines of the example above.)
- If the field doesn't exist, Django raises an error when the query runs:

```python
from sandbox.models import Task

print(Task.objects.order_by("colour"))
# django.core.exceptions.FieldError: Cannot resolve keyword 'colour' into field.
# Choices are: due_date, id, priority, status, title
```

In a real API that error would become a crash (a `500` error) for anyone who
types a wrong value. It even tells them your field names. That's one reason to
**whitelist** the allowed orderings. The other: with related models, a client
could sort by something private, like `owner__password`, and learn about it from
the order of the results. So you only allow the sorts you've chosen to support,
and quietly fall back to `id` for anything else, even for real fields like
`status` that aren't on the list.

### `params.get("name")`

- Reads a value from a dictionary, but gives `None` instead of crashing when the
  key isn't there. (`params["name"]` would raise `KeyError`.)
- Both `None` and the empty string `""` count as false in an `if`, so one `if`
  skips missing **and** empty parameters.

```python
params = {"colour": "red", "size": ""}
print(params.get("colour"))
print(params.get("size"))
print(params.get("shape"))
if params.get("size"):
    print("size was given")
else:
    print("no size, skip it")
# red
#
# None
# no size, skip it
```

The second line of output is blank: that's the empty string `""` being printed.

### `date.fromisoformat(text)`

- Turns text like `"2024-12-25"` (year-month-day) into a `date`. If the text isn't
  a valid date, it raises `ValueError`, which is exactly what test 7 wants.
- It's called on `date` itself: `date.fromisoformat(text)`, not
  `text.fromisoformat()`.

```python
print(date.fromisoformat("2024-12-25"))
print(date.fromisoformat("tomorrow"))
# 2024-12-25
# ValueError: Invalid isoformat string: 'tomorrow'
```

### `in` with a set

- `value in some_set` is `True` if the value is one of the items. `ALLOWED_ORDERING`,
  at the top of your file, is a set of the six allowed orderings.

```python
SIZES = {"small", "large"}
print("large" in SIZES)
print("huge" in SIZES)
print(None in SIZES)
# True
# False
# False
```

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The result appears in the Console tab. Delete it again afterwards.

## Step by step

Each step adds one `if` that narrows `queryset`, and stores the result back in
`queryset`. Here's the shape on different data (a plain list, not a queryset):

```python
fruits = ["apple", "banana", "cherry", "avocado"]
params = {"starts_with": "a", "max_length": ""}
if params.get("starts_with"):
    fruits = [f for f in fruits if f.startswith(params["starts_with"])]
if params.get("max_length"):
    fruits = [f for f in fruits if len(f) <= int(params["max_length"])]
print(fruits)
# ['apple', 'avocado']
```

`max_length` was empty, so its `if` was skipped.

1. **Filter by status.** If `params.get("status")` has a value, replace
   `queryset` with `queryset.filter(status=...)`, using that value. **→ test 2**
2. **Filter by priority** the same way, with the `priority` field. Because each
   filter narrows the result of the one before, both together give "AND".
   **→ tests 3 and 4**
3. **Search the title.** If `search` has a value, filter with
   `title__icontains=` that value. **→ test 5**
4. **Filter by due date.** If `due_before` has a value, turn it into a date with
   `date.fromisoformat(...)`, then filter with `due_date__lte=` that date. Don't
   catch the `ValueError`: letting it happen is what test 7 checks.
   **→ tests 6 and 7**
5. **Sort, using the whitelist.** Get `params.get("ordering")`. If it's in
   `ALLOWED_ORDERING`, sort with `queryset.order_by(...)` using it. Otherwise
   (missing, empty or not allowed), sort with `order_by("id")`.
   **→ tests 8 and 9, and keeps tests 1 and 10 passing**
6. **Return the queryset** at the end, after sorting. **→ all of tests 1-10**

## Common mistakes

- **Not storing the result**: `queryset.filter(status="todo")` on its own line does
  nothing useful. Write `queryset = queryset.filter(...)`.
- **`params["status"]` before checking**: it raises `KeyError` when the parameter
  is missing. Check with `params.get("status")` first.
- **One underscore**: `title_icontains` gives `FieldError: Cannot resolve keyword`.
  Lookups need two: `title__icontains`.
- **Passing any ordering to `order_by`**: `?ordering=nonexistent_field` then
  crashes with `FieldError`, and `?ordering=status` sorts when it shouldn't (test 9).
  Check `in ALLOWED_ORDERING` first.
- **Sorting before the `return`, but returning the old queryset**: `order_by` also
  gives back a new queryset, so return (or store) its result.

## Why it matters

Every list endpoint in a real API needs filtering, search and sorting. In real
projects, the `django-filter` package and DRF's `SearchFilter` and `OrderingFilter`
do this for you, and `OrderingFilter` has an `ordering_fields` whitelist for the
same reasons as yours. Now you know what they do underneath.
