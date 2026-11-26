"""Reading integer arguments of stdlib functions."""

from .. import converters as _converters
from ..exceptions import ConversionError, ResolutionError
from ..types import Configuration, FunctionArgs


def to_integer(
    value: Configuration, name: str, function: str, args: FunctionArgs
) -> int:
    """Convert the argument ``name`` of ``function`` to an integer.

    A ``${...}`` always gives a string, so an integer argument written as
    ``"${ n }"`` arrives as ``"3"``, not ``3``. It is converted with the
    ``integer`` converter in use (the default one if there is none), like an
    ``integer`` field in a schema, so that both ``3`` and ``"3"`` are accepted.

    Raises
    ------
    ResolutionError
        If the value can't be converted, at the function's keypath.

    """
    convert = args.resolution_context.converters.get("integer", _converters.integer)
    try:
        return convert(value)
    except ConversionError:
        raise ResolutionError(
            f"The value of '{name}' in '{function}' must be an integer, but got "
            f"{value!r}.",
            args.keypath,
        ) from None
