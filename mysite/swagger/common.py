
from __future__ import annotations

import uritemplate
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, inline_serializer
from rest_framework import serializers


# ------------------------------------------------------------ path parameters

def _path_id(name: str, description: str) -> OpenApiParameter:
    """One integer path parameter.

    ``required=True`` is explicit: a path parameter is always required in
    OpenAPI, and stating it keeps the declaration readable next to the query
    parameters, which are not.
    """
    return OpenApiParameter(
        name=name,
        type=OpenApiTypes.INT,
        location=OpenApiParameter.PATH,
        required=True,
        description=description,
    )


# Named for the rendered URL.
ID = _path_id("id", "Primary key of the addressed row.")
BRAND_PK = _path_id("brand_pk", "Primary key of the brand in the URL.")
SCHEDULE_PK = _path_id("schedule_pk", "Primary key of the schedule in the URL.")
ROLE_PK = _path_id("role_pk", "Primary key of the role in the URL.")
EMPLOYEE_PK = _path_id("employee_pk", "Primary key of the employee in the URL.")


class PathParameterSchema(AutoSchema):


    def _get_parameters(self):
        in_path = set(uritemplate.variables(self.path))
        return [
            parameter
            for parameter in super()._get_parameters()
            if parameter.get("in") != "path" or parameter.get("name") in in_path
        ]

    def _is_list_view(self, serializer=None):
        if serializer is None:
            serializer = self.get_response_serializers()
        if isinstance(serializer, serializers.BaseSerializer):
            return bool(getattr(serializer, "many", False))
        return super()._is_list_view(serializer)


# ------------------------------------------------------ per-mount operations

def by_mount(discriminator: str, present, absent):

    def _schema_class(decorator):
        def carrier(self, request, *args, **kwargs):  # pragma: no cover - never called
            raise NotImplementedError

        decorated = decorator(carrier)
        return decorated.kwargs['schema']

    present_class = _schema_class(present)
    absent_class = _schema_class(absent)

    def decorate(method):
        class MountDispatchSchema(PathParameterSchema):
            def get_operation(self, path, path_regex, path_prefix, method_, registry):
                chosen = (
                    present_class
                    if discriminator in uritemplate.variables(path)
                    else absent_class
                )
                delegate = chosen()
                delegate.view = self.view
                delegate.path = path
                delegate.path_regex = path_regex
                delegate.path_prefix = path_prefix
                delegate.method = method_.upper()
                delegate.registry = registry
                return delegate.get_operation(
                    path, path_regex, path_prefix, method_, registry
                )

        if not hasattr(method, 'kwargs'):
            method.kwargs = {}
        method.kwargs['schema'] = MountDispatchSchema
        return method

    return decorate


# ------------------------------------------------------------------- shapes

def shape(name: str, fields: dict, **kwargs):

    serializer_class = type(name, (serializers.Serializer,), dict(fields))
    return serializer_class(**kwargs), serializer_class(many=True, **kwargs)


# --------------------------------------------------------------- error bodies

ValidationErrorBody = inline_serializer(
    name="ValidationError",
    fields={"error": serializers.CharField()},
)

NotFoundBody = inline_serializer(
    name="NotFoundError",
    fields={"detail": serializers.CharField()},
)


def bad_request(description: str, examples: list[OpenApiExample] | None = None) -> OpenApiResponse:

    return OpenApiResponse(response=ValidationErrorBody, description=description, examples=examples)


def not_found(description: str) -> OpenApiResponse:

    return OpenApiResponse(response=NotFoundBody, description=description)


# Shared by every nested write.
PARENT_NOT_FOUND = not_found("A parent named in the URL does not exist.")
