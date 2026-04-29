class TravelPlannerError(Exception):
    """Base travel planner domain error."""


class IntentError(TravelPlannerError):
    """Intent understanding failed."""


class ToolCallError(TravelPlannerError):
    """Tool invocation failed."""


class StateError(TravelPlannerError):
    """State mutation or read failed."""

