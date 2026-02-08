"""Dictionary-related functions: update, update_shallow, and from_items."""

from copy import deepcopy
import typing

from ..types import (
    Function,
    FunctionArgs,
    FunctionMapping,
    ConfigurationDict,
)
from ..exceptions import ResolutionError
from .._utils import deep_update


# helpers ==============================================================================


def _all_elements_are_instances_of(container, type_):
    """Check if all elements in the container are instances of the given type."""
    return all(isinstance(element, type_) for element in container)


# functions ============================================================================


def update_shallow(args: FunctionArgs) -> ConfigurationDict:
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


def update(args: FunctionArgs) -> ConfigurationDict:
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

    return deep_update(input)


@Function.new(resolve_input=False)
def from_items(args: FunctionArgs) -> ConfigurationDict:
    """Creates a dictionary from a list of key-value pairs.

    ``args.input`` should be a list of dictionaries with two keys:

        - ``key``: the key of the dictionary
        - ``value``: the value of the dictionary

    """
    input_ = args.resolve(
        args.input,
        schema={
            "type": "list",
            "element_schema": {
                "type": "dict",
                "required_keys": {"key": {"type": "any"}, "value": {"type": "any"}},
            },
        },
    )

    assert isinstance(input_, list)

    dct = {}

    for item in input_:
        assert isinstance(item, dict)
        key = item["key"]
        assert isinstance(key, str)
        dct[key] = item["value"]

    return dct


DICT_FUNCTIONS: FunctionMapping = {
    "from_items": from_items,
    "update": update,
    "update_shallow": update_shallow,
}
