"""HTTP layer for authentication.

Plain Django JSON views: DRF is not installed. Every handler is CSRF-exempt
because these are token endpoints called by API clients, not session-cookie
form posts.
"""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from marshmallow import ValidationError

from authentication.decorators import login_required
from authentication.exceptions import AuthError
from authentication.service import AuthService
from mysite.schemas import (
    LoginSchema,
    ManagerSchema,
    RefreshSchema,
    RegisterSchema,
)

manager_schema = ManagerSchema()


def _payload(request) -> dict:
    """Parse a JSON body, tolerating an empty one."""
    if not request.body:
        return {}
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise ValidationError({"body": f"Malformed JSON: {exc.msg}"}) from exc
    if not isinstance(body, dict):
        raise ValidationError({"body": "Expected a JSON object"})
    return body


def _tokens_response(result: dict, status: int = 200) -> JsonResponse:
    return JsonResponse(
        {
            "token_type": result["token_type"],
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "expires_at": result["expires_at"].isoformat(),
            "manager": manager_schema.dump(result["manager"]),
        },
        status=status,
    )


def _handle(fn):
    """Map validation and auth failures onto status codes in one place."""
    try:
        return fn()
    except ValidationError as exc:
        return JsonResponse({"error": "Validation failed", "fields": exc.messages}, status=400)
    except AuthError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)


@csrf_exempt
@require_POST
def register(request):
    def run():
        data = RegisterSchema().load(_payload(request))
        manager = AuthService().register(
            username=data["username"],
            password=data["password"],
            email=data.get("email"),
        )
        return JsonResponse({"manager": manager_schema.dump(manager)}, status=201)

    return _handle(run)


@csrf_exempt
@require_POST
def login(request):
    def run():
        data = LoginSchema().load(_payload(request))
        result = AuthService().login(data["username"], data["password"])
        return _tokens_response(result)

    return _handle(run)


@csrf_exempt
@require_POST
def refresh(request):
    def run():
        data = RefreshSchema().load(_payload(request))
        return _tokens_response(AuthService().refresh(data["refresh_token"]))

    return _handle(run)


@csrf_exempt
@require_POST
def logout(request):
    def run():
        data = RefreshSchema().load(_payload(request))
        AuthService().logout(data["refresh_token"])
        return JsonResponse({"detail": "Logged out"}, status=200)

    return _handle(run)


@csrf_exempt
@require_POST
@login_required
def logout_everywhere(request):
    revoked = AuthService().logout_everywhere(request.manager.id)
    return JsonResponse({"detail": "Logged out everywhere", "revoked": revoked}, status=200)


@login_required
def me(request):
    return JsonResponse({"manager": manager_schema.dump(request.manager)}, status=200)
