# Django Backend Bootcamp (30 days)

A beginner-friendly four-week path from Python web fundamentals to a tested Django REST Framework Task Management API backed by SQLite.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `/api/health/` for the public health check and `/admin/` for admin. API endpoints require Basic or session authentication:

- `GET, POST /api/projects/`; detail supports `GET, PATCH, PUT, DELETE`
- `GET, POST /api/tasks/`; detail supports `GET, PATCH, PUT, DELETE`

Task filters include status, priority, project, and due_date. Lists support search,
ordering, and pagination with page_size up to 50. Every query is restricted to the
authenticated user.

## Learning path

Work through `lessons/week-1` through `lessons/week-4` in order; each day has a
lesson and exercise. Week 4 contains nine days so the path totals 30 days. Weekly
reviews are in `assessments/`, including `final.md`.

## Development commands

```bash
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py test
```

SQLite is the default for learning. Configure DJANGO_SECRET_KEY, DJANGO_DEBUG, and
DJANGO_ALLOWED_HOSTS in `.env`; never commit real secrets. For production, use a
secret manager, managed database, HTTPS, and a production WSGI/ASGI setup.
