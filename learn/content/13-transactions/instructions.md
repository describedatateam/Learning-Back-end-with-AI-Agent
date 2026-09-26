# All or nothing: transactions

## The big idea

Ada wants to send Bob 25.00. For the bank's database, that's **three separate
writes**:

1. take 25.00 off Ada's balance and save it;
2. add 25.00 to Bob's balance and save it;
3. save a log entry saying "Ada paid Bob 25.00".

Now imagine the server crashes, or Bob's account turns out not to exist, **right
after step 1**. Ada's money is gone, Bob never got it, and there's no record of
why. By default Django saves each write the moment you call `.save()`, so this can
really happen.

A **transaction** fixes it. You tell the database: "these writes belong together:
keep **all** of them, or **none** of them". If anything goes wrong in the middle,
the database **rolls back**: it undoes every write in the group, as if the transfer
had never started. It's like a bank clerk who fills in the whole transfer form in
pencil and only goes over it in pen once every line is correct. If a line is
wrong, the whole form goes in the bin.

In Django you make a transaction with a `with transaction.atomic():` block. In
this exercise you use one to make a money transfer safe.

## New words

| word | meaning |
|---|---|
| **transaction** | A group of database writes that are kept all together or not at all. |
| **atomic** | "Can't be split": the whole group happens, or none of it does. |
| **commit** | Make the writes permanent. Happens when the `atomic` block finishes normally. |
| **roll back** | Undo every write in the group. Happens when an exception leaves the `atomic` block. |
| **exception** | An error that stops the code, like `ValueError`. You can also make your own kinds. |
| **lock** | Mark a row as "in use" so another request has to wait before changing it. |
| **cents** | Balances are stored as whole numbers of cents, so `10_000` means 100.00. |

> `10_000` is just the number 10000. Python lets you put `_` in long numbers to
> make them easier to read.

## What your code receives and returns

Two models (tables) are provided in `sandbox/models.py`:

```python
class Account(models.Model):
    owner = models.CharField(max_length=100)
    balance = models.IntegerField(default=0)  # in cents: never use floats for money


class TransferLog(models.Model):
    source = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="+")
    destination = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="+")
    amount = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
```

You don't create the accounts yourself. Before each test, **the tests create two
accounts**, then call your function and pass in the account **ids** and the amount
as `source_id`, `destination_id` and `amount`:

```python
ada = Account.objects.create(owner="Ada", balance=10_000)   # 100.00
bob = Account.objects.create(owner="Bob", balance=500)      #   5.00

log = transfer(ada.id, bob.id, 2_500)
```

After that call, Ada must have `7_500` and Bob `3_000` (test 1), and `log` must be
the one new `TransferLog` row, with `source_id`, `destination_id` and `amount`
matching the call (test 2).

Every other test makes the transfer fail on purpose, then checks that **nothing
changed**: Ada still has `10_000` and Bob still has `500`.

| test | call | must raise |
|---|---|---|
| 3 | `transfer(ada.id, bob.id, amount)` for `amount` = `0`, `-50`, `12.5`, `"100"` | `ValueError` |
| 4 | `transfer(ada.id, ada.id, 100)` | `ValueError` |
| 5 | `transfer(bob.id, ada.id, 501)` (Bob only has 500) | `InsufficientFunds`, and no `TransferLog` is created |
| 6 | `transfer(ada.id, 999_999, 100)` (no such account) | `Account.DoesNotExist` |
| 7 | `transfer(ada.id, bob.id, 1_000)`, but the tests make `TransferLog.objects.create` fail with `RuntimeError("disk full")` | `RuntimeError` |

Test 7 is the important one. The money has already moved when the last step
fails, so only a transaction can undo it.

> The starter already moves money correctly, so tests 1 and 2 pass straight away.
> It just isn't **safe** yet.

## Tools you'll use

Each Console run starts with an empty database, so the examples below create
their own account.

### Your own exception: `class InsufficientFunds(Exception)`

- Already written at the top of your file. It creates a new **kind** of error with
  its own name, so code that calls `transfer` can tell "not enough money" apart
  from other problems. You use it like any other exception: `raise InsufficientFunds("...")`.

```python
class TooCold(Exception):
    pass

def check_temperature(degrees):
    if degrees < 5:
        raise TooCold(f"{degrees} degrees is too cold to plant seeds")
    return "ok"

check_temperature(12)   # 'ok'
check_temperature(2)    # the Console shows an error ending in:
                        # TooCold: 2 degrees is too cold to plant seeds
```

### `isinstance(value, int)`

- `True` if the value is a whole number. Use it to reject `12.5` and `"100"`.

```python
print(isinstance(250, int), isinstance(12.5, int), isinstance("100", int))
# True False False
```

- Common mistake: checking `amount <= 0` **first**. `"100" <= 0` crashes with a
  `TypeError`. Check the type first: `not isinstance(amount, int) or amount <= 0`
  stops at the first part when `amount` isn't a number.

### `Model.objects.get(pk=...)`

- Fetches **one** row by its id (`pk` means "primary key", the id column).
- If there's no such row, it raises `Account.DoesNotExist` by itself. You don't
  need to check for that: just let the error happen, and the transaction will undo
  anything already written.

```python
from sandbox.models import Account

Account.objects.get(pk=999)
# the Console shows: ...Account.DoesNotExist: Account matching query does not exist.
```

### `with transaction.atomic():`

- Everything **indented** under it is one transaction. If the block finishes
  normally, all its writes are kept (a `return` from inside the block counts as
  finishing normally). If an exception is raised inside it, **every**
  write in the block is rolled back, and then the exception carries on out of the
  block, so whoever called your function still sees the error.
- `transaction` is already imported at the top of your file.

Here's the "power cut" story twice, once without and once with a transaction:

```python
from django.db import transaction
from sandbox.models import Account

zoe = Account.objects.create(owner="Zoe", balance=300)

try:
    zoe.balance -= 100
    zoe.save()
    raise RuntimeError("power cut")
except RuntimeError as error:
    print("Caught:", error)

zoe.refresh_from_db()   # re-read the balance from the database
print(zoe.balance)      # 200  <- the 100 is gone!
```

```python
from django.db import transaction
from sandbox.models import Account

zoe = Account.objects.create(owner="Zoe", balance=300)

try:
    with transaction.atomic():
        zoe.balance -= 100
        zoe.save()
        raise RuntimeError("power cut")
except RuntimeError as error:
    print("Caught:", error)

zoe.refresh_from_db()
print(zoe.balance)      # 300  <- the save was rolled back
```

Both print `Caught: power cut` first. The `try` / `except` is only there so the
Console can show you the balance afterwards. In your `transfer` function you
**don't** catch the error: the tests want to see it.

### `.select_for_update()`

- Put it before `.get(...)`: `Account.objects.select_for_update().get(pk=...)`.
  It **locks** the row until the transaction ends. If two transfers from Ada's
  account arrive at the same moment, the second one waits until the first has
  finished, instead of both reading "Ada has 100.00" and both spending it.
- It only works **inside** `transaction.atomic()`. On a real database like
  PostgreSQL, using it outside raises an error. SQLite, used here, simply skips
  the lock, so no test checks it, but it's the right habit.

**Try it:** paste an example into the editor, highlight it and press
**Shift+Enter** to see the result in the Console. The Console shows what you
`print`, plus the value of the **last** highlighted line, so for `check_temperature`
highlight the `class` and `def` with one call at a time.

## Step by step

1. **Check the amount before touching the database.** If `amount` is not an
   `int`, or it's `0` or less, `raise ValueError(...)` with a message of your
   choice. **→ test 3**
2. **Check the accounts are different.** If `source_id == destination_id`,
   `raise ValueError(...)`. **→ test 4**
3. **Open a transaction.** Write `with transaction.atomic():` and move **all** the
   database code (every `get`, `save` and `create`) inside it, indented one
   level. **→ test 7**
4. **Fetch both accounts before changing anything**, using
   `Account.objects.select_for_update().get(pk=...)` for the source and then the
   destination. A missing account raises `Account.DoesNotExist` here, before any
   money has moved. **→ test 6**
5. **Check the balance.** If `source.balance < amount`,
   `raise InsufficientFunds(...)`. **→ test 5**
6. **Move the money.** Subtract `amount` from the source balance, add it to the
   destination balance, and `.save()` both. **→ test 1** (keeps passing)
7. **Record and return the log**, still inside the `with` block: keep
   `return TransferLog.objects.create(source=source, destination=destination, amount=amount)`.
   Use exactly `TransferLog.objects.create(...)`: that's the call test 7 makes
   fail on purpose. **→ tests 2 and 7**

## Common mistakes

- Putting `with transaction.atomic():` in but leaving some `save()` lines
  **outside** it (not indented). Only the indented lines are protected.
- Wrapping the transfer in `try` / `except` and hiding the error. The tests
  expect `InsufficientFunds`, `DoesNotExist` and `RuntimeError` to come out of
  your function. `atomic()` undoes the writes; it doesn't need to swallow the
  error.
- Converting the amount with `int(amount)`. That turns `12.5` into `12` and `"100"`
  into `100`, and test 3 wants those **rejected** with `ValueError`.
- Checking the balance **after** subtracting: by then you've already changed the
  source. Check `source.balance < amount` first.
- Creating the log with `TransferLog(...)` and `.save()` instead of
  `TransferLog.objects.create(...)`. It works, but then test 7 can't make it fail.

## Why it matters

Any action that writes to more than one row (placing an order and reducing stock,
signing up a user and creating their profile) needs to be all-or-nothing. In a
Django view you'd wrap that work in `transaction.atomic()` exactly like this, and
you can even make every request atomic with the `ATOMIC_REQUESTS` database setting.
