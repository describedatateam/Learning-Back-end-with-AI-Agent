# Write tests that catch bugs

## The big idea

In every exercise so far, **the tests checked your code**. Someone wrote small
programs that call your function with an input and compare the answer with the
right one. This time the roles swap: **you write the tests**, for a function that
someone else wrote.

A **test** is a tiny program that says "when I call this function with *this*,
I expect to get back *that*". You write it once, and then the computer can re-check
it in a second, every time the code changes. Real backends have hundreds or
thousands of them. They are how a team changes code without being afraid of
breaking something that used to work.

Think of a data-cleaning notebook. After cleaning, you might check
`assert df["price"].min() >= 0` to be sure no negative prices slipped through. A
test is the same idea, kept in its own file and run again and again.

A test is only useful if it **fails when the code is wrong**. A test that always
passes protects nothing. So in this exercise the tests plant bugs in the function
on purpose and check that your tests notice them.

## New words

| word | meaning |
|---|---|
| **test** | A small function that calls some code and checks the result. |
| **unit test** | A test of one small piece ("unit") of code, such as one function. |
| **slug** | The tidy, URL-friendly version of a title: `"Hello, World!"` becomes `hello-world`, as in `/blog/hello-world/`. |
| **`unittest`** | Python's built-in testing library. |
| **test case class** | A class that inherits from `unittest.TestCase`. Each method whose name starts with `test` is one test. |
| **assertion** | A check like `self.assertEqual(a, b)`. If it's false, the test **fails**. |
| **pass / fail** | A test passes when all its assertions are true, and fails as soon as one is false. |
| **bug / mutant** | A copy of the function with one small mistake planted in it. |
| **raise an error** | When a function stops and reports a problem, for example `ValueError`, instead of returning a value. |

## What your code receives and returns

This exercise works the other way round from the others.

**The function to test** is `make_slug(text)`. It lives in a file called `slugs.py`
that is already there next to yours. You don't write or change it. This is how it
behaves (these examples come from its documentation):

```python
make_slug("hello world")          # "hello-world"
make_slug("  Hello, World!  ")    # "hello-world"      lower-case, spaces at the ends removed
make_slug("Django & DRF 101")     # "django-drf-101"   a run of symbols becomes ONE "-"
make_slug("word " * 30)           # at most 50 characters, and never ends with "-"
make_slug("!!!")                  # raises ValueError: nothing usable is left
```

**Your file**, `test_slugs.py`, holds one class, `MakeSlugTests`, full of test
methods. You don't call your tests yourself. When you run the tests, the grader
loads your class and runs **all** your test methods **five times**, each time with
a different version of `make_slug` swapped in:

| run | version of `make_slug` | what's wrong with it | what your tests must do |
|---|---|---|---|
| 1 | the correct one | nothing | **all pass** |
| 2 | "no lower-case" bug | `"Hello World"` gives `"Hello-World"` | at least one **fails** |
| 3 | "no collapse" bug | `"Django & DRF 101"` gives `"django---drf-101"` (one `-` per symbol) | at least one **fails** |
| 4 | "no length limit" bug | `"word " * 30` gives a slug 149 characters long | at least one **fails** |
| 5 | "no error" bug | `"!!!"` gives `""` instead of raising `ValueError` | at least one **fails** |

So for runs 2-5, a failing test of yours is **good news**: it means your test
spotted the bug.

The tests are:

- **test 1**: your class has **at least 4** test methods.
- **test 2**: all your tests pass on the correct `make_slug` (run 1).
- **tests 3-6**: your tests catch each bug (runs 2-5).

> The starter's one example test, `make_slug("hello world") == "hello-world"`,
> passes on **all five** versions, because `"hello world"` has no capitals, no
> symbols and is short. That's why it catches none of the bugs. Each new test
> needs an input that "pokes" one specific behaviour.

## Tools you'll use

### A test case class

- You make a class that **inherits** from `unittest.TestCase` (that's what the
  `(unittest.TestCase)` after the class name means). It gives your class all the
  `assert...` methods.
- Each method whose name **starts with `test`** is one test. The name after that
  is up to you, so use it to say what the test checks.
- Every method takes `self` as its first parameter, and you call the checks as
  `self.assertEqual(...)`, with `self.` in front.

```python
import unittest

class ShoutTests(unittest.TestCase):
    def test_makes_upper_case(self):
        result = "tea".upper()          # 1. call the code
        self.assertEqual(result, "TEA")  # 2. check the answer
```

A good test has this shape: **set up the input, call the code once, check the
result**. Keep one behaviour per test, so the test's name tells you what broke.

### `self.assertEqual(actual, expected)`

- Checks that two values are equal. If they aren't, the test fails and shows you
  both values.

In the Console there's no test class around your code, so you can borrow the
checks from a plain `unittest.TestCase()` object to try them:

```python
import unittest

check = unittest.TestCase()
check.assertEqual("tea".upper(), "TEA")
print("first check passed")
check.assertEqual("tea".upper(), "Tea")
# first check passed
# AssertionError: 'TEA' != 'Tea'
```

The second line fails, and the error shows both values. That's what a failing test
looks like.

### `assertTrue`, `assertFalse` and `assertLessEqual`

- `self.assertTrue(x)` fails unless `x` is true. `self.assertFalse(x)` fails
  unless `x` is false. They're handy with methods that answer yes/no, like
  `text.endswith("-")`.
- `self.assertLessEqual(a, b)` fails unless `a <= b`. Use it with `len(...)` to
  check that something is **not too long**.

### `with self.assertRaises(SomeError):`

- Checks that the code **inside** the `with` block raises that error. If the error
  happens, the test passes. If the code finishes without raising it, the test fails.
- `with` is new syntax: write the line ending in a colon, then indent the code to
  check underneath it, like the body of an `if`.

```python
import unittest

check = unittest.TestCase()
name = "  Grace Hopper "
check.assertTrue(name.startswith(" "))
check.assertFalse(name.endswith("r"))
check.assertLessEqual(len(name.strip()), 12)
with check.assertRaises(ValueError):
    int("twelve")
print("all four checks passed")
# all four checks passed
```

On its own, `int("twelve")` would crash with `ValueError`. Inside
`assertRaises(ValueError)`, that error is exactly what was expected, so the check
passes.

### Calling `make_slug` to explore

`make_slug` is already imported at the top of your file, so you can call it in the
Console to see what it does:

```python
print(make_slug("Learn Python in 30 Days"))
print(len(make_slug("Learn Python in 30 Days")))
# learn-python-in-30-days
# 23
```

**Try it:** paste any example above into the editor, highlight it and press
**Shift+Enter**. The result appears in the Console tab. Delete the example again
afterwards, so only your real tests are left in the file.

## Step by step

Add each new test as a method inside `MakeSlugTests`, indented under the class like
`test_basic_title`. Give every test a **different name** starting with `test_`: if
two methods have the same name, the second one silently replaces the first.

1. **Keep the example test**, `test_basic_title`. It already passes on the correct
   code. **→ counts towards test 1 and test 2**
2. **Write a test for capital letters.** Call `make_slug` with a title that has
   capital letters (and maybe spaces or a comma at the ends), and use
   `assertEqual` to check it comes back all lower-case, for example
   `"  Hello, World!  "` should give `"hello-world"`. **→ test 3**
3. **Write a test for runs of symbols.** Use a title where two words are separated
   by **several** symbols in a row, like `"Django & DRF 101"` (space, `&`, space),
   and check the result has only **one** `-` there: `"django-drf-101"`. **→ test 4**
4. **Write a test for long titles.** Make a long title, for example
   `"word " * 30` (the word repeated 30 times). Store the slug in a variable, then
   check two things with two assertions: its `len(...)` is **at most 50**
   (`assertLessEqual`), and it does **not** end with `"-"` (`assertFalse` with
   `.endswith("-")`). **→ test 5**
5. **Write a test for "nothing usable".** Use `with self.assertRaises(ValueError):`
   and call `make_slug("!!!")` inside the block. **→ test 6**

With these four new tests and the example, you have 5 test methods. **→ test 1**

Now run the tests. If **test 2** fails, one of your tests is wrong about what the
correct code does: read the message, which names the test, and fix the expected
value. If one of **tests 3-6** fails, none of your tests pokes that behaviour yet.

## Common mistakes

- **A test method whose name doesn't start with `test`** (for example
  `check_lowercase`) is never run, so it can't catch anything.
- **Two methods with the same name**: only the last one counts, so you have fewer
  tests than you think (test 1).
- **Expecting the wrong answer.** If your test says `"Hello-World"` or
  `"django--drf-101"`, it fails on the correct code (test 2). Run
  `make_slug(...)` in the Console first to see the real result.
- **Calling `make_slug("!!!")` outside the `with` block**: the `ValueError` then
  crashes the test instead of being checked. Put the call on the indented line
  under `with self.assertRaises(ValueError):`.
- **Forgetting `self.`**: inside a test method, write `self.assertEqual(...)`, not
  `assertEqual(...)`, or you get `NameError`.

## Why it matters

Django has its own `TestCase` that builds on `unittest.TestCase`, and every
exercise's tests in this course are written this way. In a real project you'll
write a test for every endpoint, so that the next change can't quietly break it.
