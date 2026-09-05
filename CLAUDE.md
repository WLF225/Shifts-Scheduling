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

## Comment style

**One line, eight words, no exceptions.** Every module, class, function and
method carries exactly one docstring: a single physical line of at most eight
words. Multi-line docstrings are banned — do not write one, and compress any
you find.

- `"""Staffs, retimes, or unstaffs one shift."""` — good.
- `"""Handles the request."""` — useless, say what it actually does.
- Anything spanning two lines, or with a blank line, Args/Returns section, or
  a second sentence — wrong, regardless of how useful the content is.

This applies to `__init__`, private `_helpers`, static methods, nested classes
and package `__init__.py` files. Nothing is exempt for being obvious or small.

Inline `#` comments: only for a non-obvious *why*, one short line. Delete
decorative banners and comments that restate the code.

**The one exception is `swagger/`.** Its docstrings and `help_text` are the
API documentation — they are rendered into `schema.yml` and Swagger UI, so
they stay as long as they need to be.

Enforce it mechanically rather than by eye:

```powershell
cd mysite
..\.venv\Scripts\python.exe -c "import ast,pathlib;[print('BAD',f,n.lineno,getattr(n,'name','module')) for pat in ('components/*.py','mysite/*.py','repositories/*.py','database/*.py','middleware/*.py') for f in pathlib.Path('.').glob(pat) for n in ast.walk(ast.parse(f.read_text(encoding='utf-8'))) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and (ast.get_docstring(n) is None or len(ast.get_docstring(n).splitlines())>1 or len(ast.get_docstring(n).split())>8)]"
```

Because the rule throws away rationale, an invariant that would otherwise live
in a comment belongs in this file instead — see "Invariants that are easy to
break".

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
  the only serialization layer on the request path; viewsets call
  `XSchema(...).dump(...)` directly, or hand-build a dict via
  `components/payloads.py`. The `inline_serializer`s in `swagger/` are the one
  place DRF serializers appear, and they are documentation only — nothing
  validates or renders through them.
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

  **`ShiftRepository.for_employee`'s `INNER JOIN` on `Job` is load-bearing.**
  `Shift.job_id` is nullable because a shift is created unstaffed, so an
  `outerjoin` there would report every empty slot as time the employee is
  working. Do not "fix" it.
- `mysite/schemas.py` — one `SQLAlchemyAutoSchema` per model, `load_instance` and
  `include_fk` on, bound to the shared scoped session. Views only ever `.dump()`.
- `components/` — the domain tier, between views and repositories. One component
  per resource (`brand`, `employee`, `employee_time`, `role`, `schedule`,
  `shift`) on `BaseComponent`, which takes an optional `Session` and builds
  repositories through `_repo` — the same injection seam repositories have.
  All request validation and every business rule lives here, not in the views.
  Shared helpers: `parsing.py` (input coercion — D/M/YYYY dates, integer hours,
  case-insensitive `pick`, raising `ParseError`), `payloads.py`
  (`job_payload` / `shift_payload`, the hand-built response dicts that flatten
  a walk across tables), `exceptions.py` (framework-free, like the repository
  one).
- `mysite/views.py` — six `viewsets.ViewSet` subclasses (not `ModelViewSet`):
  Employee, EmployeeTime, Brand, Schedule, Role, Shift. They are thin: parse
  nothing, decide nothing, call one component method and dump the result. No
  view has a try/except — see "Error handling".
- `swagger/` — one module per viewset holding the drf-spectacular
  `extend_schema_view` decorator applied to it (`employee_schema`,
  `shift_schema`, …), plus `common.py` with the shared path parameters
  (`BRAND_PK`, `ID`, …) and the `shape` / `by_mount` / `not_found` /
  `bad_request` helpers. Keeping it out of `views.py` is what stops the
  annotations from burying the code.
- `middleware/db_session.py` — `DbSessionMiddleware` calls `session.remove()` in a
  `finally`, which is what makes the scoped session per-request. It must stay
  before anything that queries. `middleware.Middleware.SimpleMiddleware` is a
  request/response logger writing to `Logs.txt`.

### Routing

`mysite/urls.py` is routers only — no hand-written endpoint `path()`. Two
departures from DRF defaults, both in `SlashlessRouter` / `SlashlessNestedRouter`:

- `trailing_slash=False`. With `APPEND_SLASH` on, a POST to the slash-suffixed
  spelling 301s and drops its body, so the slash-less URL is canonical.
- `register(..., exclude_methods=[...])` drops verbs the stock route table would
  bind for one mount only (`_ExcludeMethodsMixin`). The same viewset is mounted at
  several prefixes, so a verb that is right on one is wrong on another. Used to
  remove `PUT /employees/{id}` (editing employment needs a brand) and
  `POST`/`PUT` on `employees/{employee_pk}/shifts` (a write needs a role) — all
  405 now. The brand- and role-nested equivalents are unaffected.

Top level: `employees`, `brands` — nothing else. Nested:
brands→employees/schedules, brands/schedules→roles,
brands/schedules/roles→shifts, employees→shifts/times.

Two scoping rules the tree enforces, both deliberate:

- **A schedule is always addressed under its brand.** There is no top-level
  `schedules` mount and no schedule reachable without a brand id, so a caller
  cannot read or write across brands by guessing ids. `ScheduleComponent`
  requires `brand_pk` and resolves through `schedule_for_brand`, so the rule
  survives anyone re-registering a router.
- **A shift is always addressed under its role.** There is no
  `schedules/{schedule_pk}/shifts` mount. The only other way in is
  `employees/{employee_pk}/shifts`, which is read-only (see `exclude_methods`
  above).

`urlpatterns` adds
`admin/`, the `api/v1/` mount, the two `api/v1/auth/` includes, and the schema routes.

### Session injection

`BaseRepository.__init__` takes an optional `Session`, defaulting to the shared
scoped session. This is deliberate: tests pass a transaction-scoped session and
roll back. Preserve that parameter when extending repositories.

### Error handling

`components/exceptions.py` (`ComponentError`, `ValidationError`, `NotFound`,
`Conflict`) and `repositories/exceptions.py` (`RepositoryError`, `NotFound`,
`InvalidFilter`) are both intentionally framework-free — nothing in
`components/`, `repositories/` or `database/` imports Django or DRF. Both
packages export a class named `NotFound`; `mysite/exceptions.py` imports them
under distinct aliases, so keep doing that.

`mysite/exceptions.py` is the single translation point, wired as DRF's
`EXCEPTION_HANDLER`. Component branches are checked **first** — a component is
the tier that decided what the outcome means — then repository ones:

| raised | → |
| --- | --- |
| `components.NotFound` | 404 `not_found` |
| `components.ValidationError` | 400 `{"error": ...}` |
| `components.Conflict` | 409 `conflict` |
| any other `ComponentError` | 400 `{"error": ...}` |
| `repositories.NotFound` | 404 `not_found` |
| `InvalidFilter` | 400 `invalid_filter` |
| any other `RepositoryError` | 500 `db_error` ("Database error") |

**400s answer `{"error": ...}`, not DRF's `{"detail": ...}`** — the shape the
old `_bad_request` view helper returned, kept because clients already parse it.
`_error_body` exists solely to rewrite the body; every other status keeps DRF's
shape. So no view needs a try/except and no tier below needs to import DRF.

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

**The run is clean — 0 warnings, 0 errors — and it must stay that way.** It was
not: the viewsets are plain `viewsets.ViewSet` with no `serializer_class`, and
marshmallow schemas are invisible to spectacular, so every operation once
raised `unable to guess serializer` and emitted empty bodies. The `swagger/`
package is what fixed it, and it is entirely hand-maintained:

- Every viewset carries its `extend_schema_view` decorator from `swagger/`.
  A new viewset or action without one reintroduces the warning.
- Request/response bodies are `inline_serializer`s written by hand to match
  `components/payloads.py`. They are **not** generated, so a change to a
  payload dict has to be mirrored there or the docs quietly go wrong.
- Path parameters are declared explicitly via `swagger/common.py` (`BRAND_PK`,
  `SCHEDULE_PK`, `ROLE_PK`, `EMPLOYEE_PK`, `ID`) instead of being inferred as
  `string`, and filtered per-path so a mount only advertises the ids it has.
- `by_mount` handles one view method serving two different operations
  (`EmployeeViewSet.create` is a person at the top level, an employment under a
  brand) — stacking two `@extend_schema` decorators cannot split by path.

After touching views, routers or payloads, re-run the dump and confirm it still
reports no warnings.

### Invariants that are easy to break

Docstrings across the codebase are capped at one line of ≤8 words, so these
three rules no longer fit anywhere near the code they govern. They are the ones
whose loss would cause a silent bug:

- **Contradictory staffing must stay a 400.** `ShiftComponent._staffing_intent`
  reads the staffing keys as a set: all present keys null means unstaff, all
  non-null means staff, and a *mix* is a 400. A body like
  `{"employee_id": null, "job_id": 7}` once took the unstaff branch and wrote
  `job_id = None` at HTTP 200, skipping all four eligibility rules. Do not
  "simplify" that into a per-key check.
- **One person may hold several jobs at the same brand.** Cook *and* Cashier is
  a real arrangement, so `EmployeeComponent.employ` deliberately has no
  duplicate-employment check and re-employing is a 201, never a 409. The
  missing check is the feature.
- **`ShiftComponent.list` raises `RuntimeError`, not `ValidationError`,** when
  given neither a role nor an employee. It is unreachable through routing, so a
  400 there would blame the caller for what is a wiring bug.

### Known gaps

- SQLAlchemy is pinned at 1.4.x while `repositories/base.py` is written in 2.0
  style; check compatibility before using 2.0-only APIs.
- `manage.py init_db` runs `Base.metadata.create_all` and is create-only — it
  never alters an existing table, so a changed column needs a manual `ALTER`/drop.
- `mysite/schemas.py` defines `PositionSchema`, `JobSchema` and `ShiftSchema`
  that nothing imports — Job and Shift responses are hand-built by
  `components/payloads.py` instead.
- `ShiftViewSet.update` still declares `employee_pk`, now unreachable: the
  employee mount no longer binds PUT. The parameter is live on
  `ShiftComponent.update`, so it was left in place.
- The `swagger/` bodies duplicate `components/payloads.py` by hand; nothing
  checks that the two agree.
