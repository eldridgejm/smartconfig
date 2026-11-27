"""Dictionary-related functions: update, update_shallow, and from_items."""

from copy import deepcopy

from ..types import (
    Function,
    FunctionArgs,
    FunctionMapping,
    ConfigurationDict,
)
from ..exceptions import ResolutionError
from .._utils import deep_update
from ._args import list_of


@Function.new(resolve_output=False)
def update_shallow(args: FunctionArgs) -> ConfigurationDict:
    """Update the entries of the first dictionary with the entries of the later ones.

    ``args.input`` should be a list of dictionaries.

    """
    first, *rest = list_of(dict, "dictionaries", "dict.update_shallow", args)
    first = deepcopy(first)
    for dct in rest:
        first.update(dct)
    return first


@Function.new(resolve_output=False)
def update(args: FunctionArgs) -> ConfigurationDict:
    """Recursively update the first dictionary with the entries of the later ones.

    ``args.input`` should be a list of dictionaries.

    """
    return deep_update(list_of(dict, "dictionaries", "dict.update", args))


@Function.new(resolve_input=False, resolve_output=False)
def from_items(args: FunctionArgs) -> ConfigurationDict:
    """Creates a dictionary from a list of key-value pairs.

    ``args.input`` should be a list of dictionaries with two keys:

        - ``key``: the key of the dictionary
        - ``value``: the value of the dictionary

    """
    # the input is resolved under a list schema below, whose error wouldn't say
    # which function it came from; a function call is allowed (it may produce one)
    context = args.resolution_context
    try:
        is_call = isinstance(args.input, dict) and (
            context.check_for_function_call(args.input, context.functions) is not None
        )
    except ValueError:
        is_call = False
    if not isinstance(args.input, list) and not is_call:
        raise ResolutionError(
            "Input to 'dict.from_items' must be a list of dictionaries with keys "
            "'key' and 'value'.",
            args.keypath,
        )

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
        # dictionary keys must be strings; a bare assert would give no keypath
        if not isinstance(key, str):
            raise ResolutionError(
                f"Each 'key' in 'dict.from_items' must be a string, but got {key!r}.",
                args.keypath,
            )
        dct[key] = item["value"]

    return dct


DICT_FUNCTIONS: FunctionMapping = {
    "from_items": from_items,
    "update": update,
    "update_shallow": update_shallow,
}
