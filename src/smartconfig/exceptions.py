"""Exceptions raised by smartconfig."""

from . import types as _types

# exceptions ===========================================================================


class Error(Exception):
    """A general error."""


class InvalidSchemaError(Error):
    """An error while validating a smartconfig schema."""

    def __init__(self, reason: str, keypath: _types.KeyPath):
        self.reason = reason
        self.keypath = keypath

    def __str__(self) -> str:
        dotted = _join_dotted(self.keypath)
        return f'Invalid schema at keypath: "{dotted}". {self.reason}'


class ResolutionError(Error):
    """An error while resolving a configuration."""

    def __init__(self, reason: str, keypath: _types.KeyPath):
        self.reason = reason
        self.keypath = keypath

    def __str__(self) -> str:
        dotted = _join_dotted(self.keypath)
        return f'Cannot resolve keypath "{dotted}": {self.reason}'


class TemplateRequiredError(ResolutionError):
    """A template field's value is not wrapped in ``__template__``.

    Attributes
    ----------
    variables : tuple[str, ...]
        The variables of the template field.

    """

    def __init__(
        self, reason: str, keypath: _types.KeyPath, variables: tuple[str, ...]
    ):
        super().__init__(reason, keypath)
        self.variables = variables


class ConversionError(Error):
    """Could not convert the configuration value."""


# helpers ==============================================================================


def _join_dotted(keypath: _types.KeyPath) -> str:
    """Joins a keypath into a dotted string."""
    return ".".join(str(x) for x in keypath)
