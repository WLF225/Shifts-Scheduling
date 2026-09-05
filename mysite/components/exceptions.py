"""Errors raised by the component tier.

Deliberately framework-free, for the same reason
``repositories.exceptions`` is: a component holds the business rules, and a
rule is worth testing without standing up a web layer to hear it. Nothing here
imports Django or DRF; the translation to HTTP status codes happens once, in
``mysite.exceptions.repository_exception_handler``.

The split against the repository tier is by *who knows the answer*. A
repository knows a row is absent; a component knows whether that absence is a
404 (the caller asked for something that is not there) or a rule violation. So
these three classes carry the outcomes a component can decide on its own, and
the repository errors keep meaning what they already meant.
"""


class ComponentError(Exception):
    """Base class for every component failure."""


class ValidationError(ComponentError):
    """The request cannot be honoured as written - a 400.

    Covers both malformed input (a date that will not parse) and input that
    parses but breaks a rule (an employee who is not eligible for a role).
    The distinction matters to the caller reading the message, not to the
    status code, so one class carries both.

    The HTTP status is *not* an argument: ``repository_exception_handler`` maps
    this class to 400 on its own.
    """


class NotFound(ComponentError):
    """A thing the caller addressed does not exist - a 404.

    Distinct from ``repositories.exceptions.NotFound``, which a repository
    raises about a row it was asked for by pk. This one is raised by a
    component that has already decided the *absence is the answer* - including
    absences a repository cannot see, such as a real shift reached through the
    wrong role. The message is used verbatim, because the component is the
    tier that knows which parents were searched.
    """


class Conflict(ComponentError):
    """The request collides with state that already exists - a 409.

    Reserved for "this cannot happen twice" outcomes, as distinct from
    :class:`ValidationError`'s "this request is wrong". Nothing raises it
    today: the one overlap rule in the domain (an employee double-booked) is
    reported as a 400 by ``ShiftComponent``, which is the status that endpoint
    has always returned and which this refactor is not allowed to change.
    Defined so the next such rule has somewhere correct to land.
    """
