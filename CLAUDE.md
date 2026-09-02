# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working method

Every task is done with two subagents, not one:

1. **A working agent** that implements the change.
2. **A reviewing agent** that reviews what the first one produced.

The reviewing agent must be a separate agent from the one that wrote the code -
reviewing your own diff in the same context misses what a fresh reader catches.
Report the reviewer's findings back rather than silently acting on them.

Note: the user's global `~/.claude/CLAUDE.md` prefers inline work over subagents
to avoid cold-start cost. This project rule overrides that preference here.

## Commands

All Python invocations use the venv interpreter directly (`python` on PATH is the
Windows Store stub and fails; `./mysite/manage.py ...` also fails — the shebang
is not honoured on Windows):

```powershell
.\.venv\Scripts\python.exe mysite\manage.py runserver
.\.venv\Scripts\python.exe mysite\manage.py shell
.\.venv\Scripts\python.exe mysite\manage.py init_db      # SQLAlchemy tables
.\.venv\Scripts\python.exe mysite\manage.py migrate      # Django auth tables
```

Run from the repo root with the path to `mysite\manage.py`, or `cd mysite` first.
No test suite and no linter — if you add tests, wire them against a
transaction-scoped session (see "Session injection").

## Libraries

There is **no requirements.txt**, no pyproject.toml, no setup.py — the venv at
`.venv/` is the only dependency record. Adding one is an open task.

*HTTP / API layer*
- `Django` 5.2.17 — routing, middleware, settings, WSGI, admin. Not the ORM.
- `djangorestframework` 3.18 — viewsets, `Response`, exception handling, permissions.
- `drf-nested-routers` 0.95 — the whole `brands/<id>/schedules/...` tree.

*Persistence*
- `SQLAlchemy` 1.4.54 — the scheduling domain: models, engine, scoped session, queries.
- `PyMySQL` 1.2 — the MySQL driver for *both* stacks; `mysite/mysite/__init__.py` calls
  `pymysql.install_as_MySQLdb()` before `django.db` loads so Django's backend uses it too.

*Auth* — `dj-rest-auth` 7.2 (login/logout/password/user endpoints,
`JWTCookieAuthentication`), `django-allauth` 65.19 (registration backend),
`djangorestframework-simplejwt` 5.5 (the JWT implementation). `PyJWT` and
`cryptography` come in transitively under SimpleJWT; no project code imports them.

*Schema / serialization / docs*
- `marshmallow` 4.3 + `marshmallow-sqlalchemy` 1.5 — **live**. `mysite/schemas.py` is
  the only serialization layer; viewsets call `XSchema(...).dump(...)` directly. There
  are no DRF serializers anywhere in the project.
- `drf-spectacular` 0.30 (+ `PyYAML`) — OpenAPI 3.0.3, Swagger-UI, ReDoc. See below.

**Installed but not used by any project code** (verified by grep over `mysite/`):
`Flask` 3.1 + `flasgger` 0.9 (leftovers, safe to uninstall), `pytest` 9.1 (no
tests, no config), `requests`, and the `django-stubs` /
`djangorestframework-stubs` / `types-PyYAML` stub packages (no type checker wired up).

## Architecture

Django provides the HTTP layer (routing, middleware, DRF, auth). **The scheduling
domain is SQLAlchemy, not the Django ORM.** Both ORMs share one MySQL database:
Django migrations own the auth/admin/session tables, `manage.py init_db` +
`Base.metadata.create_all` own the scheduling tables. No foreign keys cross
between them. Never add `django.db` models for the scheduling domain.

`settings.DATABASES['default']` is real MySQL (`django.db.backends.mysql`) reading
the same env vars as `database/engine.py`: `DB_NAME` (default `Schedule`),
`DB_USER` (`root`), `DB_PASSWORD` (a source literal in both files), `DB_HOST`
(`localhost`), plus `DB_PORT` (`3306`) on the Django side only. Keep them in sync.

### Import root

`mysite/` is the Python root, not the repo root. Modules import as
`database.engine`, `repositories.base`, `mysite.schemas` — so Django must be
started with `mysite/` as the working directory (or on `sys.path`).

Note the doubled name: `mysite/mysite/` is the Django project package
(settings, urls, views, schemas, exceptions); `mysite/database/`,
`mysite/repositories/`, `mysite/middleware/` are siblings. `INSTALLED_APPS`
contains contrib apps, the DRF/auth/spectacular apps, and `database` — which is
registered only so `manage.py init_db` is discovered; it has no migrations.

### Layers

- `database/engine.py` — creates the database at import time if missing (a bootstrap
  engine issues `CREATE DATABASE IF NOT EXISTS`), then exposes `engine`, `Session`,
  and a `scoped_session` named `session`. Importing it opens a DB connection.
- `database/models.py` — SQLAlchemy models on a local `Base` whose `declared_attr`
  gives every table an autoincrement `id`. Domain: Employee/Brand/Position →
  Job (the employment link) → Shift, and Brand → Schedule → Role → Shift.
- `repositories/` — `BaseRepository[ModelT]` is the only place queries are built and
  the only place `session.commit()` happens on the request path (`seed_data.py`, a
  one-off script, commits directly). Add model-specific queries as subclass methods
  rather than querying from a view.
- `mysite/schemas.py` — one `SQLAlchemyAutoSchema` per model, `load_instance` and
  `include_fk` on, bound to the shared scoped session. Views only ever `.dump()`.
- `mysite/views.py` — six `viewsets.ViewSet` subclasses (not `ModelViewSet`):
  Employee, EmployeeTime, Brand, Schedule, Role, Shift. Input coercion is
  hand-written helpers at the top of the module (D/M/YYYY dates, integer hours,
  case-insensitive keys) raising `ParseError` → 400.
- `middleware/db_session.py` — `DbSessionMiddleware` calls `session.remove()` in a
  `finally`, which is what makes the scoped session per-request. It must stay
  before anything that queries. `middleware.Middleware.SimpleMiddleware` is a
  request/response logger writing to `Logs.txt`.

### Routing

`mysite/urls.py` is routers only — no hand-written endpoint `path()`. Two
departures from DRF defaults, both in `SlashlessRouter` / `SlashlessNestedRouter`:

- `trailing_slash=False`. With `APPEND_SLASH` on, a POST to the slash-suffixed
  spelling 301s and drops its body, so the slash-less URL is canonical.
- The **list** route also accepts `PUT` → `update`, because the shift upsert is
  addressed by `(role, employee, date)` and has no pk to put in the URL.

Top level: `employees`, `brands`, `schedules/roles` (registered **before**
`schedules` so the literal wins), `schedules`. Nested: brands→employees/schedules,
brands/schedules→roles, schedules→roles/shifts, schedules/roles→shifts,
employees→shifts/times/schedules, employees/schedules→shifts. `urlpatterns` adds
`admin/`, the `api/v1/` mount, the two `api/v1/auth/` includes, and the schema routes.

### Session injection

`BaseRepository.__init__` takes an optional `Session`, defaulting to the shared
scoped session. This is deliberate: tests pass a transaction-scoped session and
roll back. Preserve that parameter when extending repositories.

### Error handling

`repositories/exceptions.py` is intentionally framework-free (`RepositoryError`,
`NotFound`, `InvalidFilter`) — nothing in `repositories/` or `database/` imports
Django or DRF. `mysite/exceptions.py` is the single translation point, wired as
DRF's `EXCEPTION_HANDLER`: `NotFound` → 404 `not_found`, `InvalidFilter` → 400
`invalid_filter`, any other `RepositoryError` → 500 `db_error` (message flattened
to "Database error"), then delegates to DRF's own handler. So no view needs a
try/except and no repository needs to import DRF.

### Authentication

`djangorestframework-simplejwt` issues the tokens, `dj-rest-auth` exposes them,
`django-allauth` backs registration. Routes are mounted at `api/v1/auth/`
(dj_rest_auth.urls) and `api/v1/auth/registration/`. `SITE_ID = 1`,
`ACCOUNT_EMAIL_VERIFICATION = 'none'`.

`REST_AUTH` sets `USE_JWT`, cookies `access` / `refresh`, and `JWT_AUTH_HTTPONLY`
— so the browser flow is JWT-in-httpOnly-cookie, not a Bearer header the JS can
read. `JWTCookieAuthentication` still accepts a Bearer header for non-browser
clients.

DRF defaults: deny-by-default (`IsAuthenticated`); public views must opt out with
`permission_classes = [AllowAny]` (dj_rest_auth's login/registration already do).
Two authentication classes: `JWTCookieAuthentication` (header or `access` cookie)
and `TokenAuthentication` (authtoken keys). `SessionAuthentication` is deliberately
omitted — it would enforce CSRF on every call. **That does not make the API
CSRF-proof:** `JWTCookieAuthentication` also authenticates off the cookie and
`JWT_AUTH_COOKIE_USE_CSRF` defaults to `False`. What blocks cross-site writes today
is `JWT_AUTH_SAMESITE` defaulting to `Lax`. If that is ever set to `None` for a
cross-origin SPA, turn on `JWT_AUTH_COOKIE_USE_CSRF` in `REST_AUTH`.

`SECRET_KEY` is the generated `django-insecure-...` literal and `DEBUG = True` —
that key signs the JWTs, so move it to an env var before this runs anywhere real.

### API docs (drf-spectacular)

`api/v1/schema/` serves the raw OpenAPI 3.0.3 document (`SpectacularAPIView`, url
name `schema`); `api/v1/schema/swagger-ui/` and `api/v1/schema/redoc/` are the two
UIs, both pointed at it by `url_name='schema'`.

`SPECTACULAR_SETTINGS` holds `TITLE`, `DESCRIPTION`, `VERSION: '1.0.0'`, and
`SERVE_INCLUDE_SCHEMA: False` (keeps the schema endpoint itself out of the schema).
`DEFAULT_SCHEMA_CLASS` is `drf_spectacular.openapi.AutoSchema`.

Dump the schema to a file:

```powershell
cd mysite
..\.venv\Scripts\python.exe manage.py spectacular --color --file schema.yml
```

The output path is relative to the CWD, so this lands at `mysite\schema.yml`
(~65 KB).

**Gotchas** (last run: 109 warnings / 33 unique, 236 errors / 6 unique — the file
is still written; these are content complaints, not a failed run):

- `unable to guess serializer` on every viewset, because they are plain
  `viewsets.ViewSet` with no `serializer_class` and marshmallow schemas
  spectacular cannot introspect. `EmployeeTimeViewSet` (`views.py:460`) is the
  worst — those endpoints emit empty/garbage bodies. Fix with `@extend_schema`.
- Untyped path parameters (`employee_pk`, `schedule_pk`, `role_pk`, `id`) default
  to `string`. Reported against `ShiftViewSet` (`views.py:663`) among others.
  Fix by typing the converter (`<int:employee_pk>`) or annotating.
- ~20 `operationId` collisions (e.g. `brands_retrieve` for both `/api/v1/brands`
  GET and `/api/v1/brands/{id}` GET) — a direct consequence of the collection-level
  PUT/GET routes sharing names with detail routes. Spectacular resolves them with
  numeral suffixes, which makes generated clients ugly.

### Known gaps

- `SPECTACULAR_SETTINGS` `TITLE` and `DESCRIPTION` are still the unedited
  placeholders `'Your Project API'` / `'Your project description'`.
- SQLAlchemy is pinned at 1.4.x while `repositories/base.py` is written in 2.0
  style; check compatibility before using 2.0-only APIs.
- `manage.py init_db` runs `Base.metadata.create_all` and is create-only — it
  never alters an existing table, so a changed column needs a manual `ALTER`/drop.
- `mysite/schemas.py` defines `PositionSchema`, `JobSchema` and `ShiftSchema`
  that no view imports.
