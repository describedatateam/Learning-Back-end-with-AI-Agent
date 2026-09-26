# Users & ownership

## The big idea

Most apps have **users**, and most data **belongs** to one of them: your notes,
your orders, your messages. That raises two jobs every backend must get right.

**1. Keep passwords safe.** You must never store a password as the user typed it.
If the database is ever leaked or copied, every account would be exposed, and
since people reuse passwords, their email and bank accounts too. Instead you store
a **hash**: the password run through a one-way scrambler. It's like a fingerprint:
the same password always gives the same fingerprint, but you can't rebuild the
password from it. To check a login, Django hashes what the user typed and compares
the two fingerprints.

**2. Only show people their own data.** Each note records its **owner**. When Ada
asks for her notes, the database query itself must say "only notes whose owner is
Ada". It's like filtering a DataFrame, `df[df["owner"] == "ada"]`, before you hand
the result to anyone.

Django ships with a ready-made `User` model and does the hashing for you, as long
as you use the right function.

## New words

| word | meaning |
|---|---|
| **user** | One account. Django's built-in `User` model has `username`, `email`, `password` and more. |
| **hash** | A scrambled, one-way version of a password. Django's look like `pbkdf2_sha256$...`. |
| **plain text** | The password exactly as typed, like `"s3cret-pass!"`. Never store this. |
| **owner** | The user a row belongs to. |
| **foreign key** | A column that points at a row in another table, like a note's `owner` pointing at a user. |
| **queryset** | What a query like `Note.objects.filter(...)` gives back: a list-like collection of rows. |
| **raise** | Stop a function and report an error, like `raise ValueError("...")`. |
| **service function** | A plain function that does one piece of app logic (create a user, fetch notes), so views stay short. |

## What your code receives and returns

You write three functions in `services.py`. **The tests call them and pass the
values in.** You don't create users or notes for the tests yourself.

The exercise gives you a `Note` model (in `sandbox/models.py`, already written):

```python
class Note(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes")
    text = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
```

`owner` is a foreign key to the `User` model (that's what `settings.AUTH_USER_MODEL`
means). `on_delete=models.CASCADE` says "if the user is deleted, delete their notes
too". `related_name="notes"` lets you go the other way: `user.notes.all()`.

These calls are copied from the tests:

| the test calls | it expects |
|---|---|
| `register_user("ada", "ada@example.com", "s3cret-pass!")` | a `User` with that username and email is returned and saved |
| then looks at `user.password` | it is **not** `"s3cret-pass!"`, and `user.check_password("s3cret-pass!")` is `True` |
| `register_user("ADA", "other@example.com", "another-pass!")` after `"ada"` exists | raises `ValueError("username already taken")`, and there's still only 1 user |
| `create_note(ada, "Buy milk")` | returns a `Note` saved in the database, with `owner` = `ada` |
| `notes_for(ada)` when Ada has "ada 1", "ada 2" and Bob has "bob 1" | only Ada's two notes |
| `notes_for(bob)` | only `["bob 1"]` |
| `notes_for(ada)` for notes made 3, 1 and 2 days ago | newest first: `["new", "middle", "old"]` |

In the ownership tests, `ada` and `bob` are `User` objects the tests made with
`User.objects.create_user(...)` before calling your function. Inside your
function they arrive as the parameter `user`.

## Tools you'll use

The top of `services.py` already imports `User` and `Note`, so you can use them
straight away. The Console starts with an empty database each run, so each
example creates its own users.

### `User.objects.create_user(username=..., email=..., password=...)`

- Creates **and saves** a user, and **hashes the password** for you.
- `user.check_password("...")` gives `True` if the text matches the stored hash.
- Common mistake: `User.objects.create(password=...)` also saves a user, but
  stores the password as **plain text**, so logins never work and the password
  is exposed. The starter uses `create`: that's the bug to fix.

```python
grace = User.objects.create_user(username="grace", email="grace@example.com", password="tea-time")
print(grace.password)                  # md5$lbkk...$b9d0...  (a hash, different every time)
print(grace.check_password("tea-time"))   # True
print(grace.check_password("coffee"))     # False

eve = User.objects.create(username="eve", password="tea-time")
print(eve.password)                    # tea-time  (plain text: wrong!)
```

The Console and the tests use a fast `md5$` hasher so they run quickly. A real
Django project uses a slow, strong one, and hashes start with `pbkdf2_sha256$`.

### `.filter(...)` and `.exists()`

- `Model.objects.filter(field=value)` gives a **queryset** of the matching rows.
- Add `__iexact` to the field name (two underscores) to match **ignoring
  upper/lower case**.
- `.exists()` on a queryset gives `True` if there's at least one row.

```python
User.objects.create_user(username="grace", email="Grace@Example.com", password="x")
print(User.objects.filter(email="grace@example.com").exists())          # False (case differs)
print(User.objects.filter(email__iexact="grace@example.com").exists())  # True
```

### `raise ValueError("message")`

- Stops the function **right there** and reports an error. Nothing after it runs.
- Whoever called the function can catch it with `try` / `except`. The tests do
  exactly that, and check the message text.

```python
def set_age(age):
    if age < 0:
        raise ValueError("age cannot be negative")
    return age

print(set_age(30))        # 30
try:
    set_age(-5)
except ValueError as error:
    print("Caught:", error)   # Caught: age cannot be negative
```

- Common mistake: `return ValueError(...)` instead of `raise`. That quietly hands
  back an error object and the function carries on as if all was fine.

### Creating a row that has an owner

- To set a foreign key, pass the **whole user object**: `owner=grace`, not
  `owner="grace"`.
- You can read it back with a dot: `note.owner.username`.
- The next example creates three notes this way.

### `.filter(owner=user)`, `.order_by(...)` and `user.notes.all()`

- `Note.objects.filter(owner=some_user)` gives only the notes that belong to
  that user. `some_user.notes.all()` gives the same rows, starting from the user.
- `.order_by("field")` sorts A to Z or oldest to newest. A `-` in front,
  `.order_by("-field")`, reverses it. You can chain it after `.filter(...)`.

```python
grace = User.objects.create_user(username="grace", password="x")
linus = User.objects.create_user(username="linus", password="x")
Note.objects.create(owner=grace, text="Water plants")
Note.objects.create(owner=linus, text="Fix kernel")
Note.objects.create(owner=grace, text="Call mum")

print(Note.objects.count())                                   # 3
print([n.text for n in Note.objects.filter(owner=grace)])     # ['Water plants', 'Call mum']
print([n.text for n in linus.notes.all()])                    # ['Fix kernel']
print([n.text for n in Note.objects.order_by("-text")])       # ['Water plants', 'Fix kernel', 'Call mum']
```

`[n.text for n in ...]` is a list comprehension: it just pulls the `text` out of
each note so the result is easy to read.

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The result appears in the Console tab.

## Step by step

### `register_user(username, email, password)`

1. **Refuse a taken username.** Before creating anything, check whether a user
   with this username already exists, **ignoring case**, using
   `.filter(username__iexact=...)` and `.exists()`. If it does,
   `raise ValueError("username already taken")`. **→ test 3**
2. **Create the user with a hashed password.** Replace the starter's
   `User.objects.create(...)` with `User.objects.create_user(...)`, passing
   `username=`, `email=` and `password=`, and return the new user.
   **→ tests 1 and 2**

### `create_note(user, text)`

3. **Create and return a note** with `Note.objects.create(...)`, passing
   `owner=user` and `text=text`. Remove the `raise NotImplementedError` line.
   **→ test 4**

### `notes_for(user)`

4. **Keep only this user's notes.** Replace `Note.objects.all()` with a
   `.filter(...)` on the `owner`. **→ test 5**
5. **Put the newest first.** Chain `.order_by(...)` on `created_at`, with a `-` so
   the newest comes first. Return the queryset. **→ test 6**

## Common mistakes

- Keeping `User.objects.create(...)`. Test 2 fails with "The password was stored
  as plain text!". Use `create_user`.
- Checking `filter(username=username)` without `__iexact`. Then `"ADA"` gets in
  because it isn't exactly `"ada"`.
- Creating the user first and checking for duplicates afterwards. By then the
  duplicate is already saved, and test 3 sees 2 users.
- `order_by("created_at")` without the `-` gives the oldest first.
- Passing a username instead of the user: `owner=user.username`. The foreign key
  needs the `User` object itself: `owner=user`.

## Why it matters

In a real Django API, the logged-in user is `request.user`, and every view that
lists or changes private data filters by it, like `Note.objects.filter(owner=request.user)`.
Hiding other people's data in the frontend isn't enough: anyone can call the API
directly. The rule has to live in the query on the server.
