"""Provides built-in functions that can be called within a configuration."""

from copy import deepcopy
import itertools
import typing

from .types import Function, FunctionArgs, RawString, RecursiveString, ConfigurationDict
from .exceptions import ResolutionError


@Function.new(resolve_input=False)
def raw(args: FunctionArgs):
    """Turn the string into a :class:`smartconfig.types.RawString` that is not interpolation/parsed."""
    # the input must be a string
    if not isinstance(args.input, str):
        raise ResolutionError("Input to 'raw' must be a string.", args.keypath)
    return RawString(args.input)


def recursive(args: FunctionArgs):
    """Turn the string into a :class:`smartconfig.types.RecursiveString` that is resolved recursively.

    ``args.input`` must be a string. If not, an error is raised.

    """
    # the input must be a string
    if not isinstance(args.input, str):
        raise ResolutionError("Input to 'recursive' must be a string.", args.keypath)
    return RecursiveString(args.input)


def splice(args: FunctionArgs):
    """Retrieves and returns the resolved configuration at the given keypath.

    ``args.input`` must be a string or an int representing the keypath to
    retrieve. The keypath must point to a place within the configuration.
    Keypaths pointing to global variables are not allowed and will result in an
    error.

    """
    if not isinstance(args.input, str) and not (
        isinstance(args.input, int) and not isinstance(args.input, bool)
    ):
        raise ResolutionError(
            "Input to 'splice' must be a string or int.", args.keypath
        )

    keypath = str(args.input)

    try:
        return args.root.get_keypath(keypath)
    except Exception:
        raise ResolutionError(f"Keypath '{keypath}' does not exist.", args.keypath)


def _all_elements_are_instances_of(container, type_):
    return all(isinstance(element, type_) for element in container)


def update_shallow(args: FunctionArgs):
    """Update the entries of the first dictionary with the entries of the later ones.

    ``args.input`` should be a list of dictionaries.

    """
    if not isinstance(args.input, list) or not _all_elements_are_instances_of(
        args.input, dict
    ):
        raise ResolutionError(
            "Input to 'update_shallow' must be a list of dictionaries.", args.keypath
        )

    if len(args.input) == 0:
        raise ResolutionError(
            "Input to 'update_shallow' must be a non-empty list of dictionaries.",
            args.keypath,
        )

    # true since we checked _all_elements_are_instances_of(args.input, dict) above
    input = typing.cast(list[ConfigurationDict], args.input)

    first = deepcopy(input[0])
    for dct in input[1:]:
        first.update(dct)

    return first


def update(args: FunctionArgs):
    """Recursively update the first dictionary with the entries of the later ones.

    ``args.input`` should be a list of dictionaries.

    """
    if not isinstance(args.input, list) or not _all_elements_are_instances_of(
        args.input, dict
    ):
        raise ResolutionError(
            "Input to 'update' must be a list of dictionaries.", args.keypath
        )

    if len(args.input) == 0:
        raise ResolutionError(
            "Input to 'update' must be a non-empty list of dictionaries.", args.keypath
        )

    # true since we checked _all_elements_are_instances_of(args.input, dict) above
    input = typing.cast(list[dict], args.input)

    def _deep_update(dictionaries: list[dict]) -> dict:
        first = deepcopy(dictionaries[0])
        for dct in dictionaries[1:]:
            for key, value in dct.items():
                if isinstance(value, dict) and isinstance(first.get(key), dict):
                    first[key] = _deep_update([first[key], value])
                else:
                    first[key] = value

        return first

    return _deep_update(input)


def concatenate(args: FunctionArgs):
    """Concatenates lists.

    ``args.input`` should be a list of lists.

    """
    if not isinstance(args.input, list) or not _all_elements_are_instances_of(
        args.input, list
    ):
        raise ResolutionError(
            "Input to 'concatenate' must be a list of lists.", args.keypath
        )

    if len(args.input) == 0:
        raise ResolutionError(
            "Input to 'concatenate' must be a non-empty list of lists.", args.keypath
        )

    # true since we checked _all_elements_are_instances_of(args.input, list) above
    input = typing.cast(list[list], args.input)

    return list(itertools.chain(*input))


def if_(args: FunctionArgs):
    """Evaluates configurations, conditionally.

    ``args.input`` should be a dictionary with three keys:
    - ``condition``: a boolean expression that is evaluated
    - ``then``: the configuration to use if the condition is true
    - ``else``: the configuration to use if the condition is false

    """
    condition = args.resolve(args.input["condition"], schema={"type": "boolean"})

    if condition:
        return args.resolve(args.input["then"])
    else:
        return args.resolve(args.input["else"])
