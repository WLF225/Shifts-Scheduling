"""OpenAPI schema declarations, kept out of the viewsets.

Every viewset in this project is a plain ``viewsets.ViewSet`` with no
``serializer_class``, because serialisation is marshmallow (``mysite/schemas.py``)
and the hand-rolled dicts in ``components/payloads.py``. drf-spectacular cannot
introspect either, so it emitted no request bodies at all for the 17 write
operations and guessed ``string`` for every path parameter. Everything it could
not infer is declared here instead.

One module per resource, each exporting a single ready-made
``@extend_schema_view(...)`` decorator named ``<resource>_schema``. ``views.py``
imports that name and applies it to the class, which keeps the decorator next
to the method it documents - a requirement, since ``@extend_schema`` only works
on the real view callable - while keeping the payload shapes, examples and
parameter declarations out of a module whose job is to stay thin. ``common.py``
holds what every resource shares: the typed path parameters and the two error
bodies.

**This package is documentation only.** Nothing here runs on the request path:
the serializers exist purely so spectacular has something to introspect, no
view passes data through them, and no declaration validates, coerces or parses
anything. The request contract is enforced by ``components/``, and these
modules only describe what that tier already does - so a change to a component
rule needs a matching edit here, which is why each module names the component
it was read from.

Deliberately not a Django app and absent from ``INSTALLED_APPS``: a plain
package with no models, no migrations and nothing for Django to discover.
"""
