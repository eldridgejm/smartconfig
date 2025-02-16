"""Provides the exceptions used by smartconfig."""

# exceptions ===========================================================================


class Error(Exception):
    """A general error."""


class InvalidSchemaError(Error):
    """An error while validating an smartconfig schema."""

    def __init__(self, reason, keypath):
        self.reason = reason
        self.keypath = keypath

    def __str__(self):
        dotted = _join_dotted(self.keypath)
        return f'Invalid schema at keypath: "{dotted}". {self.reason}'


class ResolutionError(Error):
    """An error while resolving an smartconfig."""

    def __init__(self, reason, keypath):
        self.reason = reason
        self.keypath = keypath

    def __str__(self):
        dotted = _join_dotted(self.keypath)
        return f'Cannot resolve keypath: "{dotted}": {self.reason}'


class ParseError(Error):
    """Could not parse the configuration value."""


# helpers ==============================================================================


def _join_dotted(keypath):
    """Joins a keypath into a dotted string.

    If it is already a string, it is returned as-is.
    """
    if isinstance(keypath, str):
        return keypath
    else:
        return ".".join(str(x) for x in keypath)
