"""The component tier: business rules, between the views and the repositories.

A view resolves a URL, hands the raw request body to a component, and
serialises whatever comes back. A repository builds queries. Everything
between - coercing input, deciding what is allowed, and choosing which
repository calls make up one operation - is here, in one component per
aggregate.

Two properties hold across the whole package and are worth keeping:

* **Framework-free.** Nothing under ``components/`` imports Django or DRF.
  Rules are raised as the plain exceptions in :mod:`components.exceptions` and
  turned into status codes once, in ``mysite.exceptions``.
* **Session-injected.** Every component takes an optional session and passes
  it to every repository it builds, mirroring
  :class:`repositories.base.BaseRepository`, so a test can drive a component on
  a transaction-scoped session and roll it back.

Not a Django app - a plain package, deliberately absent from
``INSTALLED_APPS``: it holds no models, no migrations and nothing Django needs
to discover.
"""
