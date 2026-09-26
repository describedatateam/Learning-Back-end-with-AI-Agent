# Kill the N+1 query

## The big idea

Your data lives in a **database**, a separate program that stores tables. Every
time your Python code needs rows from it, Django writes a question in SQL (the
database's language), sends it over, waits, and reads the answer. One round trip
like that is a **query**. A single query is fast, but each one has a fixed cost,
like a trip to the shop: buying 100 things in **one** trip is fine, making **100
trips** for one thing each is not.

The most common way to make too many trips is the **N+1 problem**. This loop looks
harmless:

```python
for task in Task.objects.all():   # 1 query: get all the tasks
    print(task.project.name)      # +1 query for EACH task, to get its project
```

With 5 tasks that's 1 + 5 = **6 queries**. With 500 tasks it's **501**. On your
laptop with a tiny database you won't notice; on a real server with real data,
the page takes seconds to load.

If you know pandas, the fix will feel familiar. Instead of looking up each task's
project one row at a time, you **merge** the two tables once
(`tasks.merge(projects, ...)`). Instead of counting each project's tasks in a loop,
you **group by** project and count (`tasks.groupby("project").size()`). Django has
the same two tools: `select_related` and `annotate`.

## New words

| word | meaning |
|---|---|
| **database** | The program that stores your tables (here, SQLite). |
| **query** | One question sent to the database and its answer: one round trip. |
| **queryset** | Django's description of a query, like `Task.objects.order_by("id")`. It only runs when you loop over it or call `list(...)` on it. |
| **N+1 problem** | 1 query for a list of N things, then 1 more query for **each** thing: N+1 in total. |
| **foreign key** | A column that points to a row in another table. Each task has a `project` foreign key. |
| **JOIN** | Combining two tables in one query, like `pd.merge`. |
| **aggregate** | Summarise many rows into one number: a count, a sum, an average. |

## What your code receives and returns

This time your functions take **no parameters**. They read from the database
instead. Two models (tables) are provided in `sandbox/models.py`:

```python
class Project(models.Model):
    name = models.CharField(max_length=120)


class Task(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
```

`related_name="tasks"` means that from a project you can reach its tasks as
`project.tasks`.

Before each test, **the tests fill the database** with this data (copied from the
tests):

| task id | project | title | done |
|---|---|---|---|
| 1 | Website | Design homepage | `True` |
| 2 | API | Add auth | `False` |
| 3 | Website | Write copy | `False` |
| 4 | API | Paginate | `True` |
| 5 | Website | Launch | `False` |

There's also a third project, **Zine**, with no tasks.

The tests then call your functions and check both the **answer** and the **number
of queries**:

```python
task_labels()
# ["Website: Design homepage", "API: Add auth", "Website: Write copy",
#  "API: Paginate", "Website: Launch"]

list(project_summaries())
# [{"name": "API", "task_count": 2, "done_count": 1},
#  {"name": "Website", "task_count": 3, "done_count": 1},
#  {"name": "Zine", "task_count": 0, "done_count": 0}]
```

The starter code **already gives these right answers**, so tests 1 and 3 pass
straight away. But it's slow:

| function | queries now (5 tasks, 3 projects) | after test 5 adds 20 more of each | goal |
|---|---|---|---|
| `task_labels()` | 1 + 5 = **6** | 1 + 25 = **26** | **1** |
| `project_summaries()` | 1 + 3 × 2 = **7** | 1 + 23 × 2 = **47** | **1** |

Tests 2, 4 and 5 use Django's `assertNumQueries(1)`, which fails if your function
runs any number of queries other than exactly one.

## Tools you'll use

Each Console run starts with an **empty** database. So first, here's some sample
data (different from the tests). Highlight it **together with** each example below.

```python
from django.db import connection
from django.db.models import Count, Q
from django.test.utils import CaptureQueriesContext
from sandbox.models import Project, Task

garden = Project.objects.create(name="Garden")
kitchen = Project.objects.create(name="Kitchen")
Task.objects.create(project=garden, title="Water plants")
Task.objects.create(project=kitchen, title="Buy flour")
Task.objects.create(project=kitchen, title="Bake bread", done=True)
```

### Counting queries: `CaptureQueriesContext(connection)`

- Records every query that runs inside the `with` block. `len(...)` gives how
  many. This is how you can see the N+1 problem for yourself.

```python
with CaptureQueriesContext(connection) as queries:
    for task in Task.objects.all():
        print(task.title, "->", task.project.name)

print(len(queries), "queries")
# Water plants -> Garden
# Buy flour -> Kitchen
# Bake bread -> Kitchen
# 4 queries      <- 1 for the tasks + 1 per task for its project
```

### `.select_related("project")`

- Tells Django: "when you fetch the tasks, fetch each task's project **in the same
  query**" (with a JOIN, like `pd.merge`). Afterwards `task.project.name` needs no
  extra trip.
- It's a **method** on a queryset, and you pass the **name of the foreign key
  field** as a string. You can chain it with other queryset methods, like
  `.filter(...)` or `.order_by(...)`.

```python
with CaptureQueriesContext(connection) as queries:
    task = Task.objects.get(title="Bake bread")
    print(task.project.name)      # Kitchen
print(len(queries), "queries")    # 2 queries

with CaptureQueriesContext(connection) as queries:
    task = Task.objects.select_related("project").get(title="Bake bread")
    print(task.project.name)      # Kitchen
print(len(queries), "queries")    # 1 queries
```

### `.annotate(new_name=Count("tasks"))`

- Adds a calculated column to every row, worked out **by the database**. With
  `Count("tasks")` the database counts each project's tasks, like
  `groupby("project").size()` in pandas, all in one query.
- `new_name` is any name you choose. It becomes an attribute of each project.
- Unlike a pandas `groupby`, projects with **no** tasks are kept, with a count
  of `0`.

```python
for project in Project.objects.annotate(n_tasks=Count("tasks")):
    print(project.name, project.n_tasks)
# Garden 1
# Kitchen 2
```

### `Count("tasks", filter=Q(...))`

- Counts only the related rows that match a condition. `Q(...)` holds the
  condition. To reach a field **on the tasks** from a project, join the names with
  a **double underscore**: `tasks__title`, `tasks__done`.

```python
for project in Project.objects.annotate(
    n_buy=Count("tasks", filter=Q(tasks__title__startswith="Buy"))
):
    print(project.name, project.n_buy)
# Garden 0
# Kitchen 1
```

### `.order_by("field")` and `.values("field", ...)`

- `.order_by("name")` sorts A to Z. `"-name"` sorts Z to A.
- `.values(...)` gives back **dictionaries** with only the fields you name, like
  picking columns and calling `df.to_dict("records")`. Annotated names work too.
- `list(...)` runs the query and gives a normal list.

```python
list(Project.objects.order_by("-name").values("name"))
# [{'name': 'Kitchen'}, {'name': 'Garden'}]
```

- Common mistake: call `.annotate(...)` **before** `.values(...)`. The other way
  round changes what gets grouped together.

**Try it:** paste the sample data and one example into the editor, highlight both
and press **Shift+Enter** to see the result in the Console. (The Console shows what
you `print`, plus the value of the last line.)

## Step by step

### `task_labels()`

1. **Fetch the projects in the same query.** In the starter, the loop goes over
   `Task.objects.order_by("id")`. Add `.select_related("project")` to that
   queryset. Keep `.order_by("id")`, so the labels stay in task id order, and keep
   the `f"{task.project.name}: {task.title}"` part as it is.
   **→ test 2, and the first half of test 5** (test 1 keeps passing)

### `project_summaries()`

2. **Start from one query that counts.** Replace the `for` loop with a single
   queryset: `Project.objects.annotate(task_count=Count("tasks"), ...)`.
   `Count` and `Q` are already imported at the top of your file.
3. **Add the done count in the same `annotate`**: a second argument,
   `done_count=Count(...)`, that counts only tasks where `done` is `True`. Use
   `filter=Q(...)` with the double-underscore path to the `done` field.
4. **Sort by name** with `.order_by("name")`, so it's API, Website, Zine.
5. **Keep only the three fields and return a list**: add
   `.values("name", "task_count", "done_count")` and return `list(...)` of the
   queryset. **→ tests 3, 4 and 5**

## Common mistakes

- Calling `.count()` or `.filter(...)` on `project.tasks` inside a loop. Each call
  is a new query: that's the N+1 problem again.
- Forgetting `.order_by("id")` in `task_labels`. The answer might come back in a
  different order and test 1 would fail.
- Writing `select_related("projects")` or `select_related(Project)`. It takes the
  **field name** as a string, and the field on `Task` is `project`.
- Writing `tasks.done` or `tasks_done` in `Q(...)`. Django's path syntax uses a
  **double** underscore: `tasks__done`.
- Using `.values(...)` before `.annotate(...)`. Put `annotate` first, then
  `order_by`, then `values`.

## Why it matters

In a DRF API, a serializer that shows `task.project.name` for a list of tasks hits
exactly this problem, one extra query per task on every page. Adding
`select_related` or `annotate` to the view's `queryset` is one of the most common
and most effective speed fixes in real Django projects. For the reverse direction
(a project with **all** its tasks), Django also has `prefetch_related("tasks")`,
which uses 2 queries in total instead of 1 + N.
