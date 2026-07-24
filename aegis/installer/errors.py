class InstallerError(RuntimeError):
    """Expected installer failure safe to display to an operator."""


class ManifestError(InstallerError):
    """A package manifest is missing or invalid."""


class DependencyError(InstallerError):
    """One or more dependencies cannot be satisfied."""


class OperationError(InstallerError):
    """A lifecycle operation failed."""
