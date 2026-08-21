"""Typed control-plane failure boundaries."""


class ControlPlaneError(Exception):
    """Base class for deterministic control-plane failures."""


class SchemaValidationError(ControlPlaneError):
    """Raised when a control-plane document fails schema validation."""


class PolicyResolutionError(ControlPlaneError):
    """Raised when policy cannot be resolved without ambiguity or weakening."""


class SecurityBoundaryError(ControlPlaneError):
    """Raised when an operation would cross an explicit security boundary."""


class StaleRevisionError(ControlPlaneError):
    """Raised when repository state changes after the operation was planned."""


class ExternalRepositoryError(ControlPlaneError):
    """Raised when a repository provider rejects or cannot complete an operation."""
