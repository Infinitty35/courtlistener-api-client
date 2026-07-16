from fastmcp.exceptions import ToolError


class SentryExemptToolError(ToolError):
    """A `ToolError` triaged as known noise; not reported to Sentry."""


def before_send(event, hint):
    """Sentry `before_send` hook: drop exempt-marked tool errors."""
    exc_info = hint.get("exc_info")
    if exc_info is not None and isinstance(exc_info[1], SentryExemptToolError):
        return None
    return event
