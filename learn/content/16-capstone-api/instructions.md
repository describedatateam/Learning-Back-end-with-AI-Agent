# Capstone: a private task API

## The big idea

This exercise puts together the pieces you built one at a time: a model, a
serializer, a viewset, a router, permissions and ownership. The result is a small
to-do API where **every user lives in their own bubble**: Ada sees, changes and
deletes only Ada's tasks, and Bob only Bob's. It's a small version of
`core/api_views.py` in this project.

Think of a hotel. Everyone walks through the same front door and uses the same
corridors (the same URLs), but your key card only opens **your** room. The front
desk (the permission check) turns away people who aren't guests at all, and the
key card (the filtered list of tasks) decides which rooms you can open.

In data-analysis terms: all users' tasks sit in one big table. For each request,
you **filter the table to the rows where `owner` is the logged-in user**, and only
ever work with that filtered table.

## New words

| word | meaning |
|---|---|
| **authenticated** | The request says who it's from (it's logged in). `request.user` is then a real user. |
| **anonymous** | A request that isn't logged in. |
| **401 Unauthorized** | "I don't know who you are. Log in first." |
| **404 Not Found** | "There's nothing here." Also used for other users' tasks, so strangers can't even tell they exist. |
| **scope a queryset** | Filter the database rows down to the ones this user may see. |
| **read-only field** | A field the API shows in responses but ignores in requests. |
| **override a method** | Write your own version of a method a class already has, so the framework calls yours instead. |
| **`self.request.user`** | Inside a viewset method: the user who sent the current request. |

## How the pieces fit together

Here's the recap map. Each row is a piece you've met before, and what it does in
this exercise:

| piece | met in exercise | its job here |
|---|---|---|
| **Model** `Task` | Design a model | The table: `owner`, `title`, `done`, `created_at`. It's **given** to you in `sandbox/models.py`. |
| **Ownership** (`owner` foreign key) | Users & ownership | Each task points to the user who owns it. `Task.objects.filter(owner=user)` gives one user's tasks. |
| **Serializer** `TaskSerializer` | Serializers, and A full CRUD API | Turns a `Task` into a dict for JSON (and checks incoming data). You add a read-only `owner`. |
| **Viewset** `TaskViewSet` | A full CRUD API | One class that handles list, create, read, update and delete. |
| **Router** | A full CRUD API | Creates the URLs `/tasks/` and `/tasks/<id>/` and connects them to the viewset. |
| **Permissions** | Who may do what? | `IsAuthenticated`: anonymous requests are turned away with 401. |
| **Scoped queryset** | new here | `get_queryset()` only returns the current user's tasks. |
| **`perform_create`** | new here | Sets `owner` to the logged-in user when a task is created. |

And here's what happens to one request, `GET /tasks/7/` sent by Ada, when task 7
belongs to Bob:

```python
# 1. Router:       "/tasks/7/" matches the detail URL, so call TaskViewSet
# 2. Permissions:  IsAuthenticated -> is someone logged in?   No -> 401. Yes (Ada) -> go on
# 3. get_queryset: take only Ada's tasks
# 4. Look up id 7 inside Ada's tasks: it isn't there -> 404
#    (if it were Ada's task: the serializer turns it into JSON -> 200)
```

The important trick is step 3. Because the viewset only ever looks inside **Ada's**
tasks, Bob's tasks are invisible for reading, changing **and** deleting. You don't
need a separate check for each action.

## What your code receives and returns

This time there's no single function to call. **The tests send HTTP requests to
the URLs your router creates**, like a real app would. They create two users, `ada`
and `bob`, and one task for each: `"Ada's task"` and `"Bob's task"`. Then they log
in as Ada (with `client.force_authenticate(ada)`) and send requests:

| test | request | expected response |
|---|---|---|
| 1 | `GET /tasks/`, **not** logged in | status **401** |
| 2 | `GET /tasks/` as Ada | **200**, and the titles are exactly `["Ada's task"]` |
| 3 | `GET /tasks/<id of Ada's task>/` | `{"id": 1, "title": "Ada's task", "done": False, "owner": "ada"}` (with the real id) |
| 4 | `POST /tasks/` with body `{"title": "New", "owner": <Bob's id>}` | **201**, and the new task's owner is **Ada**, not Bob |
| 5 | `GET /tasks/<id of Bob's task>/` | **404** |
| 6 | `PATCH` or `DELETE /tasks/<id of Bob's task>/` | **404**, and Bob's task is unchanged |
| 7 | `PATCH /tasks/<id of Ada's task>/` with `{"done": True}`, then `DELETE` it | **200**, then **204** |
| 8 | `POST /tasks/` with an empty body `{}` | **400** (a title is required) |

Notice test 3: `owner` is shown as the **username** `"ada"`, not a number. And
test 4: the body tries to make Bob the owner, and your API must ignore that.

> The starter code runs, but it's wide open on purpose: `Task.objects.all()` lets
> everyone see everything, and the viewset isn't connected to any URL yet, so every
> request gets 404.

## Tools you'll use

### Overriding a method

- A class like `ModelViewSet` already has methods that it calls for you, at the
  right moment. When you write a method **with the same name** in your class, the
  framework calls your version instead. That's called **overriding**.
- `self` is the object itself. Inside a viewset method, `self.request` is the
  request being handled right now.

```python
class Shop:
    def opening_message(self):
        return "Welcome!"

    def open(self):
        print(self.opening_message())


class TeaShop(Shop):
    def opening_message(self):          # replaces Shop's version
        return "Welcome! The tea is ready."


TeaShop().open()   # Welcome! The tea is ready.
```

`open` belongs to `Shop`, but it calls **your** `opening_message`. It's the same
with `ModelViewSet`: its built-in code calls `self.get_queryset()` and
`self.perform_create(serializer)`, and you provide your own versions.

### `serializers.ReadOnlyField(source="...")`

- Adds a field that is **shown** in responses but **ignored** in incoming data.
- `source="owner.email"` means "follow `owner`, then take its `email`". The dot
  follows the link from a task to its user.
- It's a class variable in the serializer (next to `class Meta`), and its name must
  also be listed in `Meta.fields`.

```python
from django.contrib.auth.models import User
from rest_framework import serializers
from sandbox.models import Task

grace = User.objects.create_user("grace", email="grace@example.com")
task = Task.objects.create(owner=grace, title="Write report")

class EmailDemoSerializer(serializers.ModelSerializer):
    owner_email = serializers.ReadOnlyField(source="owner.email")

    class Meta:
        model = Task
        fields = ["title", "owner_email"]

print(EmailDemoSerializer(task).data)
# {'title': 'Write report', 'owner_email': 'grace@example.com'}

incoming = EmailDemoSerializer(data={"title": "Plan", "owner_email": "evil@example.com"})
print(incoming.is_valid(), incoming.validated_data)
# True {'title': 'Plan'}      <- the read-only field was ignored
```

- Common mistake: adding the field but forgetting to add its name to `fields`.
  Then it never appears in the response.

### `serializer.save(owner=...)`

- `save()` creates the database row from the checked data. Anything you pass as a
  keyword is **added** to that data, so the server can fill in values the client
  isn't allowed to choose.

```python
from django.contrib.auth.models import User
from rest_framework import serializers
from sandbox.models import Task

grace = User.objects.create_user("grace")

class TitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "title"]

incoming = TitleSerializer(data={"title": "Plan the trip"})
incoming.is_valid()
task = incoming.save(owner=grace)
print(task.owner.username, task.title)   # grace Plan the trip
```

### `.filter(...)` and `.order_by(...)`

- You met these in "Users & ownership". `filter` keeps the matching rows, and
  `order_by("field")` sorts them (like `df.sort_values("field")` in pandas).

```python
from sandbox.models import Task
from django.contrib.auth.models import User

grace = User.objects.create_user("grace")
Task.objects.create(owner=grace, title="B task", done=True)
Task.objects.create(owner=grace, title="A task", done=True)
Task.objects.create(owner=grace, title="C task")

finished = Task.objects.filter(done=True).order_by("title")
print([t.title for t in finished])   # ['A task', 'B task']
```

### `router.register(prefix, ViewSet, basename=...)`

- Connects a viewset to URLs. It's a **method** of the router object, called with
  a dot. In "A full CRUD API" you wrote
  `router.register("books", BookViewSet, basename="book")`, which created
  `/books/` and `/books/<id>/`.
- `basename` is the name Django uses for the URLs (`book-list`, `book-detail`).
  Normally the router guesses it from the class's `queryset` line. When you replace
  that line with a `get_queryset()` method, there's nothing to guess from, and
  without `basename` your file stops with this error:

> AssertionError: \`basename\` argument not specified, and could not automatically
> determine the name from the viewset, as it does not have a \`.queryset\` attribute.

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The result appears in the Console tab.

### Check your API yourself

Paste this at the bottom of your file, highlight it and press **Shift+Enter**. It
sends a request to your API as a user called `zoe` (different users and titles from
the tests):

```python
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient
from sandbox.models import Task

zoe = User.objects.create_user("zoe")
sam = User.objects.create_user("sam")
Task.objects.create(owner=zoe, title="Water plants")
Task.objects.create(owner=sam, title="Sam's secret")

with override_settings(ROOT_URLCONF="api"):    # use the URLs from your api.py
    client = APIClient()
    client.force_authenticate(zoe)             # "log in" as zoe
    response = client.get("/tasks/")
    print(response.status_code)
    if response.status_code == 200:
        print(response.json())
```

With the starter code you'll see `404`. When you're finished you should see `200`
and then `[{'id': 1, 'title': 'Water plants', 'done': False, 'owner': 'zoe'}]`, and
no sign of Sam's secret. Django may also print a line like `Not Found: /tasks/`;
that's just its log.

> **Delete the snippet from your file before you run the tests.** Code at the
> bottom of the file runs as soon as the file loads, before the test database
> exists, so leaving it in makes the tests crash.

## Step by step

The step numbers match the `TODO` numbers in your file. Most tests can only pass
once step 5 connects the viewset to a URL, so each step says which tests it helps.

### `TaskSerializer`

**Step 1.** Add a read-only `owner` field that shows the owner's **username**: a
`ReadOnlyField` whose `source` goes from `owner` to `username`. Put it where the
TODO comment is, above `class Meta`.

**Step 2.** Add `"owner"` to the `fields` list, so it's
`["id", "title", "done", "owner"]`. **→ helps test 3**

### `TaskViewSet`

**Step 3.** Add `permission_classes = [IsAuthenticated]` as a class variable (it's
already imported). **→ helps test 1**

**Step 4.** Replace the `queryset = Task.objects.all()` line with a
`get_queryset(self)` method that returns only the tasks whose `owner` is
`self.request.user`, ordered by `"id"`. **→ helps tests 2, 5 and 6**

### The router

**Step 5.** Register the viewset on the router with the prefix `"tasks"` and
`basename="task"`, where the TODO is (above `urlpatterns`). Now the URLs exist.
**→ tests 1, 2, 3, 5, 6, 7 and 8**

### Back in `TaskViewSet`

**Step 6.** Add a `perform_create(self, serializer)` method that calls
`serializer.save(...)` with `owner` set to `self.request.user`. **→ test 4**

Test 8 (empty body gives 400) needs no extra code: `title` is required in the
model, so the serializer already rejects a missing title.

## Common mistakes

- Registering the viewset without `basename="task"` after removing `queryset`: you
  get the `AssertionError` shown above, and nothing loads.
- Keeping `queryset = Task.objects.all()` **and** forgetting `get_queryset`: every
  user sees everyone's tasks, so tests 2, 5 and 6 fail.
- Writing `request.user` instead of `self.request.user` inside the methods. There's
  no variable called `request` there, so you get a `NameError`.
- `ReadOnlyField(source="owner")` without `.username` hands over the whole user
  object instead of a name, and the response breaks. Test 3 wants `"ada"`.
- Forgetting `"owner"` in `Meta.fields`, so the field never shows up.
- Taking the owner from the request body (`request.data["owner"]`). Never trust the
  client to say who owns something.

## Why it matters

This is the shape of almost every real DRF endpoint that holds user data: log in,
scope the queryset to the user, set the owner on the server. "Broken access
control" (users reaching other users' data) is the most common serious web security
bug, and scoping `get_queryset()` is the simplest, strongest defence against it.
