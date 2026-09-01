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
`DB_HOST`, `DB_NAME`; defaults are user `root` on `localhost`, database
`Warehouse`, and a hardcoded password — see "Known gaps"). Never add
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
  and, with one exception noted under "Known gaps", the only place
  `session.commit()` happens. Per-model subclasses are
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
- The only routes are the six `/auth/` endpoints and Django's `/admin/`. The
  scheduling domain (brands, shifts, roles) has models and repositories but no
  views.
- Nothing rate-limits `/auth/login`. `refresh_tokens` rows are never pruned, and
  pruning them is not free: a revoked row *is* the reuse-detection record, so
  deleting it turns a replayed token back into a plain `InvalidToken` instead of
  a `TokenReuse` revoke-all. Only rows past `expires_at` are safe to drop.
- `RefreshTokenRepository.revoke_all_for` is the one write that bypasses
  `BaseRepository.update` — it mutates the ORM objects and calls `commit()`
  itself, after loading every row for the manager into Python rather than
  issuing a bulk `UPDATE`.

### Authentication

Bearer tokens, `/auth/` routes (`mysite/urls.py` includes `authentication.urls`),
in `mysite/authentication/`. Plain Django JSON views — DRF is not installed, and
every mutating view is `@csrf_exempt @require_POST` (`me` is the exception — only
`@login_required`, so it answers any verb). Paths have **no trailing slash**, and
`APPEND_SLASH` is left at its default `True` with `CommonMiddleware` active: a POST
to `/auth/login/` raises `RuntimeError` under `DEBUG = True`, and in production
301-redirects to `/auth/login` **dropping the body**. Always post slash-less.

**Endpoints** (bodies validated by the marshmallow schemas in `mysite/schemas.py`):

| Method | Path | Body | Success |
|---|---|---|---|
| POST | `/auth/register` | `username` (3-100), `password` (8-128), optional `email` | `201 {"manager": {...}}` |
| POST | `/auth/login` | `username`, `password` | `200` token pair |
| POST | `/auth/refresh` | `refresh_token` | `200` token pair |
| POST | `/auth/logout` | `refresh_token` | `200 {"detail": "Logged out"}` |
| POST | `/auth/logout-all` | — (needs access token) | `200 {"detail": ..., "revoked": <int>}` |
| GET | `/auth/me` | — (needs access token) | `200 {"manager": {...}}` |

The token-pair shape is `{token_type: "Bearer", access_token, refresh_token,
expires_at (ISO, access-token expiry), manager}`. `ManagerSchema` excludes
`password_hash`. Errors: `400 {"error": "Validation failed", "fields": {...}}`
on marshmallow failure; otherwise `{"error": "<message>"}` with the status off
`AuthError.status` — 401 default (`InvalidCredentials`, `InvalidToken`,
`TokenReuse`), 403 `InactiveAccount`, 409 `UsernameTaken`.

**Access token** (`authentication/tokens.py`): HS256 JWT signed with
`settings.SECRET_KEY`. Payload is exactly `sub` (manager id, **a string**),
`type: "access"`, `iat`, `exp`. Lifetime is `ACCESS_TOKEN_LIFETIME =
timedelta(minutes=15)` in that module. `decode_access_token` verifies signature
and `exp` via PyJWT, then rejects a wrong `type` or unparseable `sub`; every
failure becomes `InvalidToken`. No DB round-trip for the token itself.

**Refresh token**: `secrets.token_urlsafe(48)`, `REFRESH_TOKEN_LIFETIME =
timedelta(days=14)`. Only `sha256(raw).hexdigest()` is persisted, in
`refresh_tokens` (`manager_id`, `token_hash` unique+indexed, `expires_at`,
`revoked_at`); the raw string is returned once and unrecoverable. `AuthService.refresh`
looks the hash up, then: unknown → `InvalidToken`; `revoked_at` already set →
`revoke_all_for(manager_id)` and `TokenReuse`; expired → `InvalidToken`;
manager missing → `InvalidToken`, inactive → `InactiveAccount`. Otherwise it
revokes the presented token and issues a fresh pair — rotation on every use.
MySQL returns naive datetimes, so `_expired` re-tags them as UTC before comparing.

**Passwords**: `django.contrib.auth.hashers.make_password` / `check_password`
(PBKDF2), called only in `authentication/service.py`. Login hashes a dummy even
when the username is unknown so wrong-user and wrong-password take the same time.
`AUTH_PASSWORD_VALIDATORS` in `settings.py` is **not** applied — `RegisterSchema`
only enforces length 8-128.

**Request lifecycle**: `BearerAuthMiddleware` splits `HTTP_AUTHORIZATION` on the
first space, requires scheme `bearer` (case-insensitive) and a non-blank token,
and always sets both `request.manager` and `request.auth_error` (either may be
`None`). It is permissive by design: a bad token sets `auth_error` and leaves
`manager = None` so public routes still work. A valid token is loaded through
`ManagerRepository().get(...)` — one DB query per authenticated request — and an
inactive or missing manager yields `auth_error = "Account is unavailable"`.
`@login_required` (`authentication/decorators.py`) returns
`401 {"error": <auth_error or "Authentication required">}` when `request.manager`
is `None`.

Note the asymmetry: `logout-all` is the only revoking endpoint that authenticates
by **access** token; `logout` and `refresh` authenticate by the refresh token in
the body. `logout` always returns `200`, even for an unknown or already-spent
token, so a client cannot tell "revoked" from "never valid". The refresh token's
own expiry is never returned — only the access token's `expires_at` — so clients
cannot know when re-login becomes necessary.

**Typical flow**: `POST /auth/register` (returns the manager only, no tokens) →
`POST /auth/login` → store both tokens → send
`Authorization: Bearer <access_token>` to `/auth/me` → on 401, `POST /auth/refresh`
with the refresh token (the old one is now dead — replace both) → `POST /auth/logout`
with the current refresh token, or `/auth/logout-all` with a live access token.

**Gotchas**:
- `BearerAuthMiddleware` must stay **after** `middleware.db_session.DbSessionMiddleware`
  in `settings.MIDDLEWARE`; it queries on every request and the scoped session
  would leak between requests otherwise.
- Logout and `logout-all` revoke refresh tokens only; an already-issued access
  token stays valid for the rest of its 15 minutes. There is no `jti` claim and
  no denylist, so a single access token cannot be revoked. Only rotating
  `SECRET_KEY` truly kills one (and it kills every outstanding access token).
  Setting `is_active = False` is weaker: the middleware re-checks it every request,
  so `@login_required` routes start 401ing, but the JWT itself stays valid — any
  route reading `request.manager` without the decorator, or any consumer verifying
  the JWT itself, still accepts it.
- `exp`/`iat` are plain UTC timestamps, there is no `nbf`, and `jwt.decode` is
  called without `leeway`, so server clock skew directly shortens or extends token
  validity. Pass `leeway=` in `decode_access_token` if that ever bites.
- `AuthService.refresh` checks `revoked_at` **before** expiry, so replaying a token
  that is both expired and revoked still triggers the full `revoke_all_for` storm.
- The package is `authentication`, not `auth`: the label `auth` collides with
  `django.contrib.auth` and Django refuses to start. The URL prefix is still `/auth/`.
- `python manage.py init_db` runs `Base.metadata.create_all` for **all** models,
  `managers` and `refresh_tokens` included (there are no Django migrations). It is
  create-only — it never alters an existing table, so a changed column needs a
  manual `ALTER`/drop.
