# How Describe lessons are written

Each exercise's `instructions.md` is the lesson the learner reads next to the editor.
These rules come from watching a real learner work through exercise 1 with the tutor.

## Who the learner is

- New to backend development and web concepts (HTTP, servers, APIs, databases).
- Self-taught Python from **data analysis**: knows strings, string methods, lists,
  dictionaries, loops, numpy/pandas/matplotlib/seaborn. Less sure about functions
  and parameters, tuple unpacking, classes, and reading unfamiliar syntax.
- Learns best from a concrete example first, then the rule.

## What went wrong before (don't repeat it)

1. The learner never saw the **actual input** the function receives. They asked
   "where is the raw that I need to be splitting?"
2. It wasn't explained that **the tests call your function** and pass the input in
   as a parameter, so a parameter like `raw` only exists inside the function.
3. New functions and syntax appeared with **no "how to use it"**, which led to
   `raw.urlsplit(...)` instead of `urlsplit(raw)`, `parts["path"]` instead of
   `parts.path`, and confusion between `()`, `[]` and `{}`.
4. Web concepts (head, body, request) were assumed, not explained.
5. Vague verbs ("collect the headers") and functions with no stated purpose
   ("I don't know why this function was written").
6. Steps weren't connected to the tests, so the learner couldn't tell which step
   fixes which failing test.
7. Loops that build a dictionary were hard. Show a small worked example with
   different data first.

## Lesson structure (use these headings, in this order)

```markdown
# <Title>

## The big idea
2-4 short paragraphs. What this is and why a backend needs it. Use one everyday
analogy, and link to data analysis where it's natural ("this is like cleaning a
messy text column into tidy fields").

## New words
A short table or bullet list: every new term, one plain sentence each.

## What your code receives and returns
Show the exact call the tests make and a real input value, copied from
grader_tests.py, and the exact expected result. Say plainly: "You don't create
this input yourself. The tests call your function and pass it in as `raw`."

## Tools you'll use
One small card per new function, method or piece of syntax:
### `name(...)`
- What it does, in one sentence.
- How to call it (function vs method, which brackets), with a tiny runnable example
  and its output shown as a comment.
- A common mistake, if there is one.
End with: "Try it: paste the example into the editor, highlight it and press
**Shift+Enter** to see the result in the Console."

## Step by step
Numbered steps with specific verbs ("make a dictionary where...", not "collect").
After each step, say which tests it should make pass, e.g. **→ tests 1-2**.
Before a loop, show a mini worked example of the same pattern on different data.

## Common mistakes
3-5 bullets of the mistakes a beginner is likely to make here, and how to spot them.

## Why it matters
1-2 sentences connecting the exercise to real Django/DRF work.
```

## Rules

- Keep the exact function names, file names, error messages and requirements the
  grader tests check. Rewrite the explanation, not the task.
- Test numbers match the grader's test method numbers (test_01 is test 1).
- Try-it examples must run on their own (define any sample data inline) and must
  not give away the full solution. Use different data from the exercise, or show
  one tool at a time.
- The Console (Shift+Enter) shows what the code `print()`s plus the value of the
  **last** highlighted line only. When an example has several results, `print()`
  each one and show its output as a comment.
- Short sentences, plain words, no jargon without a definition. Aim for a lesson a
  beginner can read in 10-15 minutes.
- Markdown only: headings, lists, tables, fenced code blocks marked `python` (these
  get syntax colours), `>` notes. No HTML.
- Indent nested list items by **4 spaces** (the renderer ignores 2- or 3-space
  nesting). A numbered list may start at any number, e.g. `7.` continues from 6.
- Don't mention XP or the grading system beyond "the tests".
