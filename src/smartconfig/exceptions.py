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
    parameters : tuple[str, ...]
        The parameters of the template field.

    """

    def __init__(
        self,
        reason: str,
        keypath: _types.KeyPath,
        parameters: tuple[str, ...],
    ):
        super().__init__(reason, keypath)
        self.parameters = parameters


class UnexpectedTemplateError(ResolutionError):
    """A ``__template__`` wrapper where none belongs.

    Attributes
    ----------
    enclosing : KeyPath | None
        The keypath of the template that contains the wrapper, or ``None`` if the
        wrapper is not inside a template.

    """

    def __init__(
        self,
        reason: str,
        keypath: _types.KeyPath,
        enclosing: _types.KeyPath | None,
    ):
        super().__init__(reason, keypath)
        self.enclosing = enclosing


class UndefinedNameError(ResolutionError):
    """A ``${ ... }`` uses a name that is not defined.

    Attributes
    ----------
    name : str
        The undefined name.
    available : tuple[str, ...]
        The names that were available, in lookup order: local variables, the keys
        of the root, then the global variables (not counting Jinja's own names,
        like ``range``).

    """

    def __init__(
        self,
        reason: str,
        keypath: _types.KeyPath,
        name: str,
        available: tuple[str, ...],
    ):
        super().__init__(reason, keypath)
        self.name = name
        self.available = available


class ConversionError(Error):
    """Could not convert the configuration value."""


# helpers ==============================================================================


def _join_dotted(keypath: _types.KeyPath) -> str:
    """Joins a keypath into a dotted string."""
    return ".".join(str(x) for x in keypath)
