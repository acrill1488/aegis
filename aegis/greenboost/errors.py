"""Public exception hierarchy for the GreenBoost integration protocol."""


class GreenBoostError(Exception):
    """Base class for every error exposed by GBIP."""


class ConnectionError(GreenBoostError):
    """GreenBoost could not be reached."""


class TimeoutError(GreenBoostError):
    """A bounded GreenBoost operation timed out."""


class ProtocolError(GreenBoostError):
    """GreenBoost returned an invalid or unexpected response."""


class AuthenticationError(GreenBoostError):
    """GreenBoost rejected the configured credentials."""


class ReservationDenied(GreenBoostError):
    """GreenBoost denied a resource reservation."""


class NodeUnavailable(GreenBoostError):
    """The requested GreenBoost node is unavailable."""
