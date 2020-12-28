# exceptions
# --------------------------------------------------------------------------------------


class Error(Exception):
    """Generic error."""


class ValidationError(Error):
    """Publication does not satisfy schema."""


class DiscoveryError(Error):
    """A configuration file is not valid."""

    def __init__(self, msg, path):
        self.path = path
        self.msg = msg

    def __str__(self):
        return f"Error reading {self.path}: {self.msg}"


class BuildError(Error):
    """Problem while building the artifact."""
