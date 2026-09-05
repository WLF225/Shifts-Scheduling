"""Input coercion for the component tier.

The clients that drive this API send dates as ``D/M/YYYY`` and times as bare
integer hours, and they are inconsistent about key casing (``job_ID`` vs
``job_id``). Rather than scatter that tolerance through the components, every
conversion is a helper here.

These functions used to live at the top of ``mysite/views.py``, where each
caller wrapped them in ``try/except ParseError`` and turned the message into a
400 by hand. They moved down a tier with the rules they serve: a component
takes the raw request body and owns every question about it, so the view has
nothing left to coerce and nothing left to catch.
"""
from __future__ import annotations

from datetime import date as date_type, datetime, time as time_type
from typing import Any, Iterable

from components.exceptions import ValidationError


class ParseError(ValidationError):
    """A request field could not be coerced into the type the column needs.

    A :class:`~components.exceptions.ValidationError` subclass rather than the
    ``ValueError`` it used to be, which is what retires the ``try/except`` that
    once sat around every parse call. The handler already maps
    ``ValidationError`` to 400, so an unparseable field now answers 400 by
    falling all the way out of the component - and the distinct class is kept
    because "this text is not a date" is worth telling apart from "this
    employee is not eligible" when reading a traceback.
    """


# Accepted date spellings; D/M/YYYY is tried first.
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y")

# Accepted time spellings for the string form.
TIME_FORMATS = ("%H:%M:%S", "%H:%M", "%H")


def pick(data: dict[str, Any], *names: str, default: Any = None) -> Any:
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return default


def has_key(data: dict[str, Any], *names: str) -> bool:
    lowered = {str(key).lower() for key in data}
    return any(name.lower() in lowered for name in names)


def present_keys(data: dict[str, Any], *names: str) -> list[str]:
    lowered = {str(key).lower() for key in data}
    return [name for name in names if name.lower() in lowered]


def parse_date(value: Any, field: str = "date") -> date_type:
    """Coerce ``value`` into a ``date``. Accepts ``D/M/YYYY`` and ISO."""
    if isinstance(value, date_type) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ParseError(f"{field} is required")
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ParseError(
        f"{field} {text!r} is not a date; expected D/M/YYYY or YYYY-MM-DD"
    )


def parse_time(value: Any, field: str = "time") -> time_type:

    if isinstance(value, time_type):
        return value
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ParseError(f"{field} is required")
    if isinstance(value, bool):
        raise ParseError(f"{field} {value!r} is not a time")
    if isinstance(value, int):
        return _hour(value, field)
    if isinstance(value, float):
        if value != int(value):
            raise ParseError(f"{field} {value!r} is not a whole hour")
        return _hour(int(value), field)
    text = str(value).strip()
    if text.isdigit():
        return _hour(int(text), field)
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ParseError(
        f"{field} {text!r} is not a time; expected an hour 0-24 or HH:MM"
    )


def parse_int(value: Any, field: str) -> int:

    if isinstance(value, bool):
        raise ParseError(f"{field} {value!r} is not an integer")
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ParseError(f"{field} {value!r} is not an integer") from None


def require_text(value: Any, field: str, max_length: int = 100) -> str:

    if value is None:
        raise ParseError(f"{field} is required")
    text = str(value).strip()
    if not text:
        raise ParseError(f"{field} must not be blank")
    if len(text) > max_length:
        raise ParseError(f"{field} must be at most {max_length} characters")
    return text


def parse_modes(raw: Any, allowed: Iterable[str]) -> list[str]:

    allowed = [mode.lower() for mode in allowed]
    if raw is None or not str(raw).strip():
        return list(allowed)
    modes = []
    for part in str(raw).split(","):
        mode = part.strip().lower()
        if not mode:
            continue
        if mode not in allowed:
            raise ParseError(
                f"mode {part.strip()!r} is not valid; expected one of "
                + ", ".join(sorted(allowed))
            )
        if mode not in modes:
            modes.append(mode)
    if not modes:
        raise ParseError("mode must name at least one of " + ", ".join(sorted(allowed)))
    return modes


def body_dict(data: Any) -> dict[str, Any]:

    return data if isinstance(data, dict) else {}


def _hour(hour: int, field: str) -> time_type:

    if hour == 24:
        return time_type(23, 59)
    if not 0 <= hour <= 23:
        raise ParseError(f"{field} {hour!r} is not an hour between 0 and 24")
    return time_type(hour, 0)
