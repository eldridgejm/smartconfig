"""Provides the default function that can be called within a configuration."""

from copy import deepcopy
import itertools
import typing

from .types import Function, FunctionArgs, RawString
from .exceptions import ResolutionError


@Function.new(resolve_input=False)
def raw(args: FunctionArgs):
    """Do not resolve the value."""
    # the input must be a string
    if not isinstance(args.input, str):
        raise ResolutionError("Input to 'raw' must be a string.", args.keypath)
    return RawString(args.input)


def splice(args: FunctionArgs):
    """Retrieves and returns the resolved configuration at the given keypath.

    The keypath may either point to a place inside the configuration, in which case
    it should start with `this`, or it may point to a place in the external
    variables that were passed along with the resolution context.

    """
    if not isinstance(args.input, str):
        raise ResolutionError("Input to 'splice' must be a string.", args.keypath)
    try:
        return args.root.get_keypath(args.input)
    except KeyError:
        raise ResolutionError(f"Keypath '{args.input}' does not exist.", args.keypath)


def _all_elements_are_instances_of(container, type_):
    return all(isinstance(element, type_) for element in container)


def update_shallow(args: FunctionArgs):
    """Update the entries of the first dictionary with the entries of the later ones.

    args.input should be a list of dictionaries.

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
    args.input = typing.cast(list[dict], args.input)

    first = deepcopy(args.input[0])
    for dct in args.input[1:]:
        first.update(dct)

    return first


def update(args: FunctionArgs):
    """Recursively update the first dictionary with the entries of the later ones.

    args.input should be a list of dictionaries.

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
    args.input = typing.cast(list[dict], args.input)

    def _deep_update(dictionaries: list[dict]) -> dict:
        first = deepcopy(dictionaries[0])
        for dct in dictionaries[1:]:
            for key, value in dct.items():
                if isinstance(value, dict) and isinstance(first.get(key), dict):
                    first[key] = _deep_update([first[key], value])
                else:
                    first[key] = value

        return first

    return _deep_update(args.input)


def concatenate(args: FunctionArgs):
    """Concatenate lists.

    args.input should be a list of lists.

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
    args.input = typing.cast(list[list], args.input)

    return list(itertools.chain(*args.input))
