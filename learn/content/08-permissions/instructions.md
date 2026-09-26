# Who may do what?

## The big idea

Your API from the last exercise lets anyone change or delete any book. A real API
needs rules: *you* may edit *your* notes, but not somebody else's.

Answering "may this request go ahead?" takes two separate questions:

1. **Authentication: who are you?** The request carries some proof, like a
   username and password or a token. Django checks it and works out which user is
   calling. The result is stored on the request as **`request.user`**.
2. **Permissions: are you allowed to do this?** Now that we know who it is, a
   **permission class** looks at the user, the HTTP method and sometimes the object,
   and answers **yes** (`True`) or **no** (`False`).

Think of an office building. Showing your badge at the door is authentication. The
rules about which rooms your badge opens are permissions. In this exercise you
write the rules. The badge check is already done for you.

## New words

| word | meaning |
|---|---|
| **authentication** | Working out *who* is making the request. |
| **permission** | A rule that decides whether this user may do this action. |
| **`request.user`** | The user making the request. Django fills it in before your code runs. |
| **`AnonymousUser`** | What `request.user` is when nobody logged in: a stand-in "nobody" user. |
| **`is_authenticated`** | `True` for a real, logged-in user; `False` for `AnonymousUser`. |
| **`is_staff`** | `True` for team members (admins), `False` for normal users. |
| **owner** | The user an object belongs to, stored in a field like `note.owner`. |
| **safe method** | A method that only reads: `GET`, `HEAD`, `OPTIONS`. The others (`POST`, `PUT`, `PATCH`, `DELETE`) change data. |
| **`401` / `403`** | The replies DRF sends when a permission says no: `401` usually means "log in first", `403` means "you're logged in, but not allowed". |

## What your code receives and returns

You don't call these methods yourself, and there is no real web request. **The
tests build fake requests and call your methods directly**, passing the request
in as `request` and the object in as `obj`. This is how they set things up
(copied from the tests):

```python
owner = User.objects.create_user("owner", password="x")
other = User.objects.create_user("other", password="x")
staff = User.objects.create_user("staff", password="x", is_staff=True)
note = SimpleNamespace(owner=owner)           # a pretend object with an owner

request = RequestFactory().patch("/notes/1/")  # a fake PATCH request
request.user = other                           # made by the user "other"
```

Then they call, for example:

```python
IsOwnerOrReadOnly().has_permission(request, None)                 # view is None
IsOwnerOrReadOnly().has_object_permission(request, None, note)
```

and check that you return `True` or `False`:

| test | method called | who | request | expected |
|---|---|---|---|---|
| 1 | `IsOwnerOrReadOnly.has_permission` | `AnonymousUser()` | `GET` | `False` |
| 2 | `IsOwnerOrReadOnly.has_permission` | `other` | `GET` | `True` |
| 3 | `IsOwnerOrReadOnly.has_object_permission` | `other` | `GET`, `HEAD`, `OPTIONS` | `True` |
| 4 | `IsOwnerOrReadOnly.has_object_permission` | `owner` | `PATCH`, `PUT`, `DELETE` | `True` |
| 5 | `IsOwnerOrReadOnly.has_object_permission` | `other` | `PATCH`, `PUT`, `DELETE` | `False` |
| 6 | `IsStaffForDelete.has_permission` | `other` | `GET`, `POST`, `PATCH` | `True` |
| 7 | `IsStaffForDelete.has_permission` | `staff` / `other` / `AnonymousUser()` | `DELETE` | `True` / `False` / `False` |

> The starter's methods all `return True`, so tests 2, 3, 4 and 6 already pass.
> That's fine: your job is to make the "no" answers (tests 1, 5 and 7) come out
> `False` without breaking the "yes" ones.

## Tools you'll use

### A permission class: `has_permission` and `has_object_permission`

- A permission class inherits from `BasePermission` and has up to two methods.
  In a real API, DRF calls them for you at two moments:

```python
class SomePermission(BasePermission):
    def has_permission(self, request, view):
        # Called for EVERY request, before anything else happens.
        # "May this user use this endpoint at all?"
        return True

    def has_object_permission(self, request, view, obj):
        # Called only when the request is about ONE object,
        # like GET /notes/1/ or DELETE /notes/1/, after that object is loaded.
        # "May this user do this to THIS object?"
        return True
```

- If a method returns `False`, DRF stops and sends back an error (`401` or `403`),
  and the view's code never runs.
- Both methods get the `request`, so they can read `request.method` (like
  `"DELETE"`) and `request.user`. `has_object_permission` also gets `obj`, the
  object being read or changed. `view` is the view being called; you won't need it.
- You switch permissions on in a view with a list, for example
  `permission_classes = [IsOwnerOrReadOnly, IsStaffForDelete]`. Every class in the
  list must say yes.

The examples below all run in the Console: Django's user model and a practice
database are ready for you, and the imports at the top of your file are loaded.
The database starts empty on every run.

### `request.user`, `.is_authenticated` and `.is_staff`

- `request.user` is a user object. Read facts about it with a dot, like
  `request.user.is_staff`. These are **attributes**, not methods, so there are no
  brackets: `is_authenticated`, not `is_authenticated()`.

```python
from django.contrib.auth.models import AnonymousUser, User

ada = User.objects.create_user("ada", password="x")
boss = User.objects.create_user("boss", password="x", is_staff=True)
visitor = AnonymousUser()
print(ada.is_authenticated, ada.is_staff)
print(boss.is_authenticated, boss.is_staff)
print(visitor.is_authenticated, visitor.is_staff)
# True False
# True True
# False False
```

They're already `True` or `False`, so you can `return` them directly.

### `SAFE_METHODS` and `in`

- `SAFE_METHODS` is imported at the top of your file. It's a tuple of the methods
  that only read. `x in something` checks whether `x` is one of the items.

```python
print(SAFE_METHODS)
print("GET" in SAFE_METHODS)
print("PATCH" in SAFE_METHODS)
# ('GET', 'HEAD', 'OPTIONS')
# True
# False
```

`request.method` is always in capitals, like `"GET"` or `"DELETE"`.

### Comparing users with `==`

- `obj.owner == request.user` is `True` when they are the same user. Django
  compares users by their id, so two separate objects for the same user count as
  equal.
- The tests' "object" is a `SimpleNamespace`: a quick pretend object whose
  attributes you read with a dot, just like a real model.

```python
from types import SimpleNamespace
from django.contrib.auth.models import User

ada = User.objects.create_user("ada", password="x")
grace = User.objects.create_user("grace", password="x")
recipe = SimpleNamespace(title="Pancakes", owner=ada)
print(recipe.title, recipe.owner)
print(recipe.owner == ada)
print(recipe.owner == grace)
print(recipe.owner == User.objects.get(username="ada"))
# Pancakes ada
# True
# False
# True
```

### Calling a permission method yourself

Here's a made-up permission with a different, silly rule, called the same way the
tests call yours:

```python
from django.contrib.auth.models import User
from django.test import RequestFactory

class NoMondays(BasePermission):
    def has_permission(self, request, view):
        return request.user.username != "monday"

ada = User.objects.create_user("ada", password="x")
request = RequestFactory().post("/recipes/")
request.user = ada
print(request.method, request.user)
print(NoMondays().has_permission(request, None))
# POST ada
# True
```

`RequestFactory().post(...)` makes a fake `POST` request; `.get(...)`, `.patch(...)`
and `.delete(...)` make the other kinds.

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The result appears in the Console tab. Delete it again afterwards.

## Step by step

### `IsOwnerOrReadOnly`

1. **In `has_permission`, let only logged-in users in.** Replace `return True` so
   it returns `request.user.is_authenticated`. An anonymous visitor gets `False`,
   anyone logged in gets `True`. **→ tests 1 and 2**
2. **In `has_object_permission`, let everyone read.** First check whether
   `request.method` is in `SAFE_METHODS`. If it is, return `True` straight away.
   **→ test 3**
3. **Otherwise, only the owner may change it.** After that `if`, the request
   must be a change (`PATCH`, `PUT` or `DELETE`). Return whether the object's owner,
   `obj.owner`, is the same user as `request.user`. **→ tests 4 and 5**

Here's the same "answer early, otherwise decide" shape on different data:

```python
def can_enter(age, has_ticket):
    if age < 5:
        return True        # small children always get in
    return has_ticket      # everyone else needs a ticket

print(can_enter(3, False), can_enter(30, True), can_enter(30, False))
# True True False
```

### `IsStaffForDelete`

This class only needs `has_permission`: the rule doesn't depend on which object.

4. **Only staff may delete.** If `request.method` is `"DELETE"`, return
   `request.user.is_staff`. For every other method, return `True`.
   `AnonymousUser` has `is_staff` too (it's always `False`), so you don't need a
   separate check for it. **→ tests 6 and 7**

## Common mistakes

- **Brackets after an attribute**: `request.user.is_authenticated()` gives
  `TypeError: 'bool' object is not callable`. Write it without `()`.
- **Checking the owner in `has_permission`**: there is no `obj` there. The owner
  check belongs in `has_object_permission`.
- **Returning nothing**: if a path through your method has no `return`, it
  returns `None`, which DRF treats as "no". Make sure every path returns
  `True` or `False`.
- **Lower-case methods**: `request.method == "delete"` is never true.
  `request.method` is `"DELETE"`.
- **Comparing usernames by hand**, like `obj.owner.username == request.user.username`,
  works but is fragile. Compare the users themselves: `obj.owner == request.user`.

## Why it matters

Every real API has rules like these. In a DRF view you'd write
`permission_classes = [IsOwnerOrReadOnly, IsStaffForDelete]`, and DRF would call
your methods on every request, answering `401` or `403` for you when they say no.
