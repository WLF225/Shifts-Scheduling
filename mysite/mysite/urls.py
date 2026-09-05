"""Router tree for the versioned API."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework import routers
from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework_nested import routers as nested_routers
from django.urls import path, include


from mysite.views import (
    BrandViewSet,
    EmployeeTimeViewSet,
    EmployeeViewSet,
    RoleViewSet,
    ScheduleViewSet,
    ShiftViewSet,
)


class _ExcludeMethodsMixin:
    """Drops verbs a single registration must not bind."""

    def __init__(self, *args, **kwargs):
        """Defaults trailing_slash off and tracks exclusions."""
        kwargs.setdefault("trailing_slash", False)
        super().__init__(*args, **kwargs)
        self._excluded = {}

    def register(self, prefix, viewset, basename=None, exclude_methods=None):
        """Registers a mount, recording its excluded methods."""
        if exclude_methods:
            self._excluded[basename] = set(exclude_methods)
        super().register(prefix, viewset, basename=basename)

    def _routes_without(self, excluded):
        """Stock routes with the excluded methods removed."""
        return [
            route._replace(
                mapping={
                    method: action
                    for method, action in route.mapping.items()
                    if method not in excluded
                }
            )
            if isinstance(route, routers.Route)
            else route
            for route in self.routes
        ]

    def get_urls(self):
        """Builds urls one registration at a time."""
        if not self._excluded:
            return super().get_urls()

        registry, stock, root = self.registry, self.routes, self.include_root_view
        collected = []
        try:
            self.include_root_view = False
            for entry in registry:
                self.registry = [entry]
                self.routes = self._routes_without(self._excluded.get(entry[2], set()))
                collected += super().get_urls()
        finally:
            self.registry, self.routes = registry, stock
            self.include_root_view = root

        if self.include_root_view:
            root_url = path('', self.get_api_root_view(api_urls=collected),
                            name=self.root_view_name)
            collected += (
                format_suffix_patterns([root_url])
                if self.include_format_suffixes
                else [root_url]
            )
        return collected


class SlashlessRouter(_ExcludeMethodsMixin, routers.DefaultRouter):
    """Top-level router with no trailing slash."""


class SlashlessNestedRouter(_ExcludeMethodsMixin, nested_routers.NestedDefaultRouter):
    """Nested router with no trailing slash."""


router = SlashlessRouter()
router.register('employees', EmployeeViewSet, basename='employees', exclude_methods=['put'])
router.register('brands', BrandViewSet, basename='brands')

brands_router = SlashlessNestedRouter(router, 'brands', lookup='brand')
brands_router.register('employees', EmployeeViewSet, basename='brand-employees')
brands_router.register('schedules', ScheduleViewSet, basename='brand-schedules')

brand_schedules_router = SlashlessNestedRouter(brands_router, 'schedules', lookup='schedule')
brand_schedules_router.register('roles', RoleViewSet, basename='brand-schedule-roles')

brand_schedule_roles_router = SlashlessNestedRouter(brand_schedules_router, 'roles', lookup='role')
brand_schedule_roles_router.register('shifts', ShiftViewSet, basename='brand-schedule-role-shifts')

employees_router = SlashlessNestedRouter(router, 'employees', lookup='employee')
employees_router.register('shifts',ShiftViewSet,basename='employee-shifts',exclude_methods=['post', 'put'])
employees_router.register('times', EmployeeTimeViewSet, basename='employee-times')

api_v1_urls = (
    router.urls
    + brands_router.urls
    + brand_schedules_router.urls
    + brand_schedule_roles_router.urls
    + employees_router.urls
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(api_v1_urls)),
    path('api/v1/auth/', include('dj_rest_auth.urls')),
    path('api/v1/auth/registration/', include('dj_rest_auth.registration.urls')),
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
