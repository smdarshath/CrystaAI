class CrystaError(Exception):
    """Base error for expected, user-explainable failures."""


class ToolUnavailable(CrystaError):
    """A tool cannot run (missing dependency, feature disabled, offline...)."""


class LLMUnavailable(ToolUnavailable):
    pass


class ToolNotPermitted(CrystaError):
    """An agent tried to use a tool that is not in its permitted list."""


class PermissionDenied(CrystaError):
    pass


class PathNotAllowed(PermissionDenied):
    pass


class NetworkError(CrystaError):
    pass


class Cancelled(CrystaError):
    pass


class NeedsConfirmation(CrystaError):
    def __init__(self, token, description, risk, tool):
        super().__init__(description)
        self.token = token
        self.description = description
        self.risk = risk
        self.tool = tool
