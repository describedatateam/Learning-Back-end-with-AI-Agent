# Validate input with serializers

## The big idea

Anything a client sends your API is **untrusted**. It might come from your own
website, but it might just as well come from a script, a typo, an old app version
or someone trying to break things. A title might be missing, a date might be
`"next friday"`, a priority might be `"URGENT!!!"`. If you save that straight
into the database, you get broken data, crashes, or worse.

It's the same as receiving a messy spreadsheet from someone else: before you
analyse it, you check every column has the right type, fill in defaults for
blanks, and reject rows that make no sense. You never assume the data is clean.

In Django REST Framework (DRF), the tool for this is a **serializer**. You write
a class that lists the fields you expect and the rules for each one. You hand it
the incoming data, ask "is this valid?", and it gives you either **clean data**
(with the right Python types) or a **dictionary of error messages**, one list per
field, ready to send back with a 400 status.

A serializer is like a bouncer with a checklist: each field is checked on its
own first, then the whole thing is checked together.

```mermaid
flowchart LR
    D["Data from the client"] --> F["Check each field"]
    F --> W["validate(): check fields together"]
    W -->|is_valid() is True| C["validated_data: clean values"]
    F -->|a rule fails| E["errors: one list per field"]
    W -->|a rule fails| E
    E --> R["400 Bad Request"]
```

## New words

| word | meaning |
|---|---|
| **untrusted input** | Data from outside your server. Assume it can be missing, the wrong type or wrong on purpose. |
| **serializer** | A DRF class that describes the expected fields and checks incoming data against them. |
| **validation** | Checking data against rules. It either passes or produces error messages. |
| **`is_valid()`** | Runs all the checks. Gives `True` or `False`. |
| **`validated_data`** | The clean data (a dict) after `is_valid()` returned `True`. |
| **`errors`** | A dict of field name to a list of messages. Empty, `{}`, when all is fine. |
| **`ValidationError`** | The error you `raise` inside a serializer to say "this is not allowed". |
| **`attrs`** | Short for attributes: the dict of all field values, passed to `validate()`. |

## What your code receives and returns

You write a class, `TaskSerializer`, in `serializers.py`. **The tests create it
with some data and check the result.** Every test does this (copied from the tests):

```python
serializer = TaskSerializer(data={"title": "Write docs", "priority": "low", "due_date": TOMORROW})
serializer.is_valid()
serializer.errors            # the test checks this dict
serializer.validated_data    # and sometimes this one
```

`TOMORROW` and `YESTERDAY` are worked out from today's date when the tests run, as
text like `"2026-09-27"` (the format is `YYYY-MM-DD`).

| data the test sends | expected result |
|---|---|
| `{"title": "Write docs", "priority": "low", "due_date": TOMORROW}` | valid; `validated_data["due_date"]` is a real `date` for tomorrow |
| `{"title": "Write docs"}` | valid; `validated_data["priority"]` is `"medium"` |
| `{"priority": "low"}` | error on `title` (it's required) |
| `{"title": "  ab  "}` | error on `title`: `"Title must be at least 3 characters."` |
| `{"title": "  Deploy  "}` | valid; `validated_data["title"]` is `"Deploy"` |
| `{"title": "Write docs", "priority": "urgent"}` | error on `priority` |
| `{"title": "Write docs", "due_date": None}` | valid (and the serializer must have a `due_date` field) |
| `{"title": "Write docs", "due_date": YESTERDAY}` | error on `due_date`: `"Due date cannot be in the past."` |
| `{"title": "Fix outage", "priority": "high"}` | error on `due_date`: `"High priority tasks need a due date."` |
| `{"title": "Fix outage", "priority": "high", "due_date": TOMORROW}` | valid |

The error messages must match **exactly**, full stop included.

## Tools you'll use

`serializers.py` already imports `serializers` (from DRF) and `date`, so you can
use them straight away. The examples below make their own small serializers with
different fields, so you can see each tool on its own.

### A `Serializer` class, `is_valid()`, `validated_data` and `errors`

- You write a class that **inherits** from `serializers.Serializer` (the name in
  brackets after the class name). Each field is one line, just like a model.
- You **use** it by calling the class with `data=...`, then `.is_valid()`.

```python
class PetSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=20)
    age = serializers.IntegerField(min_value=0)

good = PetSerializer(data={"name": "  Rex  ", "age": "3"})
print(good.is_valid())        # True
print(good.validated_data)    # {'name': 'Rex', 'age': 3}

bad = PetSerializer(data={"age": -1})
print(bad.is_valid())         # False
print(bad.errors)
# {'name': [ErrorDetail(string='This field is required.', code='required')],
#  'age': [ErrorDetail(string='Ensure this value is greater than or equal to 0.', code='min_value')]}
```

Notice three free checks: `CharField` **strips spaces** (`"  Rex  "` became
`"Rex"`), `"3"` was turned into the number `3`, and every field is **required**
unless you say otherwise. An `ErrorDetail` is just a message; `str(...)` of it
gives the plain text.

### `serializers.ChoiceField(choices=[...], default=...)`

- Only accepts one of the listed values. `default=` is used when the field is
  missing (and makes it not required).

### `serializers.DateField(required=False, allow_null=True)`

- Accepts a date written as `"YYYY-MM-DD"` and turns it into a Python `date`.
- `required=False`: the field may be left out. `allow_null=True`: it may be sent
  as `None` (`null` in JSON). They're two different options, like `null` and
  `blank` on a model.

```python
class ShirtSerializer(serializers.Serializer):
    size = serializers.ChoiceField(choices=["S", "M", "L"], default="M")
    gift_date = serializers.DateField(required=False, allow_null=True)

s = ShirtSerializer(data={})
s.is_valid()
print(s.validated_data)   # {'size': 'M'}  (default used; gift_date left out)

s = ShirtSerializer(data={"size": "XL", "gift_date": "2026-12-24"})
s.is_valid()
print(s.errors)           # {'size': [ErrorDetail(string='"XL" is not a valid choice.', code='invalid_choice')]}

s = ShirtSerializer(data={"size": "L", "gift_date": "2026-12-24"})
s.is_valid()
print(s.validated_data)   # {'size': 'L', 'gift_date': datetime.date(2026, 12, 24)}

s = ShirtSerializer(data={"gift_date": None})
s.is_valid()
print(s.validated_data)   # {'size': 'M', 'gift_date': None}
```

### `date.today()` and comparing dates

- `date.today()` gives today's date. Dates compare like numbers: earlier is
  "smaller", so `some_date < date.today()` means "in the past".

```python
print(date.today())                          # e.g. 2026-09-26
print(date(2020, 1, 31) < date.today())      # True (2020 is in the past)
```

### `def validate_<field>(self, value):` (one field)

- A method named `validate_` plus a field name. DRF calls it **after** that
  field's own checks passed, with the cleaned value (already stripped, already
  a `date`, and so on).
- If the value is bad, `raise serializers.ValidationError("message")`. If it's
  fine, you **must `return` the value** (you may return a tidied version).

```python
class UsernameSerializer(serializers.Serializer):
    username = serializers.CharField()

    def validate_username(self, value):
        if value.lower() == "admin":
            raise serializers.ValidationError("That name is reserved.")
        return value.lower()

s = UsernameSerializer(data={"username": " ADMIN "})
print(s.is_valid(), s.errors)
# False {'username': [ErrorDetail(string='That name is reserved.', code='invalid')]}
s = UsernameSerializer(data={"username": " Grace "})
print(s.is_valid(), s.validated_data)
# True {'username': 'grace'}
```

- For a field with `allow_null=True`, `value` can be `None`. Check for that
  before comparing, since `None < date.today()` crashes.

### `def validate(self, attrs):` (several fields together)

- Runs **last**, once every field passed. `attrs` is a dict of all the clean
  values, so you can compare fields with each other.
- To attach the error to one field, raise with a **dict**:
  `serializers.ValidationError({"field_name": "message"})`.
- If all is fine, **`return attrs`**.
- Use `attrs.get("name")`, not `attrs["name"]`, for optional fields: a field
  that was left out is simply not in the dict.

```python
class TripSerializer(serializers.Serializer):
    start = serializers.IntegerField()
    end = serializers.IntegerField()

    def validate(self, attrs):
        if attrs["end"] < attrs["start"]:
            raise serializers.ValidationError({"end": "The trip can't end before it starts."})
        return attrs

s = TripSerializer(data={"start": 10, "end": 4})
print(s.is_valid())   # False
print(s.errors)       # {'end': [ErrorDetail(string="The trip can't end before it starts.", code='invalid')]}
```

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The result appears in the Console tab.

## Step by step

All of this goes inside `class TaskSerializer(serializers.Serializer):`. The
`title` field is already there, and it already makes **tests 3 and 5** pass
(`CharField` is required and strips spaces by default).

1. **Add `priority`.** A `ChoiceField` with the choices `"low"`, `"medium"` and
   `"high"`, and `default="medium"`. **→ tests 2 and 6**
2. **Add `due_date`.** A `DateField` that can be left out **and** can be `None`.
   **→ tests 1 and 7**
3. **Write `validate_title(self, value)`.** If `value` has fewer than 3 characters
   (`len(value) < 3`), raise `serializers.ValidationError("Title must be at least 3 characters.")`.
   Otherwise return `value`. The spaces are already stripped when it arrives.
   **→ test 4**
4. **Write `validate_due_date(self, value)`.** If `value` is not `None` and is
   earlier than `date.today()`, raise `"Due date cannot be in the past."`.
   Otherwise return `value`. **→ test 8**
5. **Write `validate(self, attrs)`.** If `attrs.get("priority")` is `"high"` and
   there's no due date (`attrs.get("due_date")` is missing or `None`), raise a
   `ValidationError` with a **dict** that puts
   `"High priority tasks need a due date."` on the `"due_date"` key.
   Otherwise return `attrs`. **→ test 9**

## Common mistakes

- Forgetting `return value` at the end of `validate_title`: the title silently
  becomes `None`. Forgetting `return attrs` in `validate()`: DRF stops with an
  `AssertionError` saying `.validate() should return the validated data`.
- `required=False` without `allow_null=True` (or the other way round). Test 2
  leaves `due_date` out and test 7 sends `None`, so the field needs both.
- Comparing `value < date.today()` without checking for `None` first. It crashes
  with a `TypeError` when `due_date` is `None`.
- Raising the high-priority error as a plain string in `validate()`. It then lands
  under `non_field_errors` instead of `due_date`. Use the dict form.
- Naming the method `validate_titles` or `title_validate`. DRF only finds it if
  it's exactly `validate_` + the field name.

## Why it matters

In a real DRF view you write `serializer = TaskSerializer(data=request.data)`,
then `if not serializer.is_valid(): return Response(serializer.errors, status=400)`.
That's all the checking you did by hand in exercise 2, now in one reusable class.
Frontend checks are a courtesy to the user; the serializer on the server is what
actually protects your data.
