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
Windows Store stub and fails):

```powershell
.\.venv\Scripts\python.exe mysite\manage.py runserver
.\.venv\Scripts\python.exe mysite\manage.py shell
```

Run Django commands from the repo root with the path to `mysite\manage.py`, or
`cd mysite` first. There is no requirements.txt, no test suite, and no linter
configured yet — if you add tests, wire them so they can run against a
transaction-scoped session (see "Session injection" below).

## Architecture

Django provides only the HTTP layer (routing, middleware, WSGI). **All persistence
is SQLAlchemy, not the Django ORM.** `settings.DATABASES` still points at the
stock sqlite3 default and is effectively unused; the real database is MySQL,
configured by env vars in `mysite/database/engine.py` (`DB_USER`, `DB_PASSWORD`,
`DB_HOST`, `DB_NAME`, defaulting to `root`/`Warehouse` on localhost). Never add
`django.db` models or migrations — they will not reflect the real schema.

### Import root

`mysite/` is the Python root, not the repo root. Modules import as
`database.engine`, `repositories.base`, `mysite.schemas` — so Django must be
started with `mysite/` as the working directory (or on `sys.path`). A bare
`from database...` import fails if you run from the repo root without that.

Note the doubled name: `mysite/mysite/` is the Django project package
(settings, urls, wsgi, schemas); `mysite/database/`, `mysite/repositories/`,
`mysite/middleware/` are siblings of it, not Django apps. `INSTALLED_APPS`
contains only contrib apps.

### Layers

- `database/engine.py` — creates the MySQL database at import time if missing
  (a bootstrap engine issues `CREATE DATABASE IF NOT EXISTS`), then exposes
  `engine`, `Session`, and a `scoped_session` named `session`. Importing this
  module opens a DB connection as a side effect.
- `database/models.py` — SQLAlchemy models on a local `Base` whose `declared_attr`
  gives every table an autoincrement `id`. Domain: Employee/Brand/Position →
  Job (the employment link) → Shift, and Brand → Schedule → Role → Shift.
- `repositories/` — `BaseRepository[ModelT]` is the only place queries are built
  and the only place `session.commit()` happens. Per-model subclasses are
  currently one-liners setting `model`; add model-specific queries as methods
  there rather than querying from a view.
- `mysite/schemas.py` — `marshmallow_sqlalchemy` `SQLAlchemyAutoSchema` per model,
  all with `load_instance = True` and `include_fk = True`, bound to the shared
  scoped session. Serialization layer; there is no DRF installed.
- `middleware/db_session.py` - `DbSessionMiddleware` calls `session.remove()` in a
  `finally`, which is what makes the scoped session per-request. Registered in
  `settings.MIDDLEWARE` alongside `middleware.Middleware.SimpleMiddleware`, a
  request/response logger writing to `Logs.txt`.

### Session injection

`BaseRepository.__init__` takes an optional `Session`, defaulting to the shared
scoped session. This is deliberate: tests pass a transaction-scoped session and
roll back. Preserve that parameter when extending repositories.

### Error handling

`repositories/exceptions.py` is intentionally framework-free (`RepositoryError`,
`NotFound`, `InvalidFilter`) — nothing in `repositories/` or `database/` may
import Django. Its docstring points at a `mysite.exeptions.repository_exception_handler`
for HTTP translation; **that module does not exist yet** and is the intended place
for the repository-error → status-code mapping.

### Known gaps

- SQLAlchemy is pinned at 1.4.x while `repositories/base.py` is written in 2.0
  style; check compatibility before using 2.0-only APIs.
- `settings.py` still has the generated `SECRET_KEY` inline and `DEBUG = True`.
  The secret key signs the access JWTs, so anyone holding it can mint valid
  tokens - move it to an env var before this runs anywhere real. Rotating it
  invalidates every outstanding access token by design.
- `database/engine.py` defaults `DB_PASSWORD` to a literal in the source.
- There is no test suite. The auth flow was verified with a throwaway script,
  not something committed; `python manage.py test` finds nothing.
- Only the auth endpoints exist. The scheduling domain (brands, shifts, roles)
  has models and repositories but no views.

### Authentication

Bearer tokens, `/auth/` routes, in `mysite/authentication/`:

- Access token: stateless HS256 JWT, 15 minutes, signed with `SECRET_KEY`,
  verified with no database round-trip.
- Refresh token: opaque random string, 14 days, stored only as a SHA-256 hash
  in `refresh_tokens`. Rotated on every use; presenting a spent one revokes
  every live token for that manager.
- Passwords hashed with Django's PBKDF2 hashers in `authentication/service.py`
  and nowhere else.
- `BearerAuthMiddleware` sets `request.manager` (or `None`); the
  `@login_required` decorator in `authentication/decorators.py` enforces access.

The package is `authentication`, not `auth`: the label `auth` collides with
`django.contrib.auth` and Django refuses to start. The URL prefix is still
`/auth/`.

Create the tables with `python manage.py init_db` (there are no Django
migrations - the Django ORM is unused).
