"""Input coercion for the component tier."""
from __future__ import annotations

from datetime import date as date_type, datetime, time as time_type
from typing import Any, Iterable

from components.exceptions import ValidationError


class ParseError(ValidationError):
    """A request field could not be coerced."""


# Accepted date spellings; D/M/YYYY is tried first.
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y")

# Accepted time spellings for the string form.
TIME_FORMATS = ("%H:%M:%S", "%H:%M", "%H")


def pick(data: dict[str, Any], *names: str, default: Any = None) -> Any:
    """First value matching any name, case-insensitively."""
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return default


def has_key(data: dict[str, Any], *names: str) -> bool:
    """True if any of these names is present."""
    lowered = {str(key).lower() for key in data}
    return any(name.lower() in lowered for name in names)


def present_keys(data: dict[str, Any], *names: str) -> list[str]:
    """Which of these names the body actually carries."""
    lowered = {str(key).lower() for key in data}
    return [name for name in names if name.lower() in lowered]


def parse_date(value: Any, field: str = "date") -> date_type:
    """Coerce a value into a date, accepting D/M/YYYY."""
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
    """Coerce into a time, accepting bare hours."""
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
    """Coerce a value into an int, rejecting bools."""
    if isinstance(value, bool):
        raise ParseError(f"{field} {value!r} is not an integer")
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ParseError(f"{field} {value!r} is not an integer") from None


def require_text(value: Any, field: str, max_length: int = 100) -> str:
    """Require non-blank text within a length limit."""
    if value is None:
        raise ParseError(f"{field} is required")
    text = str(value).strip()
    if not text:
        raise ParseError(f"{field} must not be blank")
    if len(text) > max_length:
        raise ParseError(f"{field} must be at most {max_length} characters")
    return text


def parse_modes(raw: Any, allowed: Iterable[str]) -> list[str]:
    """Split a comma list into allowed mode names."""
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
    """The request body as a dict, else empty."""
    return data if isinstance(data, dict) else {}


def _hour(hour: int, field: str) -> time_type:
    """Turn hour 0-24 into a time."""
    if hour == 24:
        return time_type(23, 59)
    if not 0 <= hour <= 23:
        raise ParseError(f"{field} {hour!r} is not an hour between 0 and 24")
    return time_type(hour, 0)
