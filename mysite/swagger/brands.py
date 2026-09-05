"""Schema for ``BrandViewSet``.

Contract read off ``components/brand.py``. ``create`` requires both ``name``
and ``location``: ``Brand.location`` is NOT NULL at the column, and the
component calls ``require_text`` on it so an omitted location answers 400
rather than reaching the insert and turning into an IntegrityError 500.
"""
from __future__ import annotations

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

from swagger.common import ID, bad_request, not_found, shape

BrandResponse, BrandListResponse = shape(
    "Brand",
    {
        "id": serializers.IntegerField(read_only=True),
        "name": serializers.CharField(),
        "location": serializers.CharField(),
    },
)

BrandRequest = inline_serializer(
    name="BrandRequest",
    fields={
        # Both required; lengths mirror the columns.
        "name": serializers.CharField(max_length=100),
        "location": serializers.CharField(max_length=255),
    },
)


brand_schema = extend_schema_view(
    list=extend_schema(
        summary="List brands",
        description="Every brand. An empty result is an empty list, not a 404.",
        responses={200: BrandListResponse},
    ),
    retrieve=extend_schema(
        summary="Retrieve a brand",
        parameters=[ID],
        responses={200: BrandResponse, 404: not_found("No brand with this id.")},
    ),
    create=extend_schema(
        summary="Create a brand",
        description=(
            "Both `name` and `location` are required. `location` is NOT NULL at "
            "the column, so omitting it is a 400 rather than a 500."
        ),
        request=BrandRequest,
        responses={
            201: OpenApiResponse(response=BrandResponse, description="Brand created."),
            400: bad_request("`name` or `location` is missing or blank."),
        },
        examples=[
            OpenApiExample(
                "Create a brand",
                value={"name": "Bean & Board", "location": "12 Nile St, Cairo"},
                request_only=True,
            ),
            OpenApiExample(
                "Missing location",
                value={"error": "location is required"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    ),
)
