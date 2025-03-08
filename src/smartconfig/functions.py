"""Provides built-in functions that can be called within a configuration."""

from copy import deepcopy
import itertools
import typing

from .types import (
    Function,
    FunctionArgs,
    RawString,
    RecursiveString,
    ConfigurationDict,
    ConfigurationList,
    Configuration,
)
from .exceptions import ResolutionError


# helpers ==============================================================================


def _all_elements_are_instances_of(container, type_):
    """Check if all elements in the container are instances of the given type."""
    return all(isinstance(element, type_) for element in container)


# functions ============================================================================


@Function.new(resolve_input=False)
def raw(args: FunctionArgs) -> Configuration:
    """Turn the string into a :class:`smartconfig.types.RawString` that is not interpolation/parsed."""
    # the input must be a string
    if not isinstance(args.input, str):
        raise ResolutionError("Input to 'raw' must be a string.", args.keypath)
    return RawString(args.input)


def recursive(args: FunctionArgs) -> Configuration:
    """Turn the string into a :class:`smartconfig.types.RecursiveString` that is resolved recursively.

    ``args.input`` must be a string. If not, an error is raised.

    """
    # the input must be a string
    if not isinstance(args.input, str):
        raise ResolutionError("Input to 'recursive' must be a string.", args.keypath)
    return RecursiveString(args.input)


def splice(args: FunctionArgs) -> Configuration:
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


def if_(args: FunctionArgs) -> Configuration:
    """Evaluates configurations, conditionally.

    ``args.input`` should be a dictionary with three keys:

        - ``condition``: a boolean expression that is evaluated
        - ``then``: the configuration to use if the condition is true
        - ``else``: the configuration to use if the condition is false

    """
    # check that the input is valid
    if not isinstance(args.input, dict):
        raise ResolutionError("Input to 'if' must be a dictionary.", args.keypath)

    # check that the keys are exactly "condition", "then" and "else"
    if set(args.input.keys()) != {"condition", "then", "else"}:
        raise ResolutionError(
            "Input to 'if' must be a dictionary with keys 'condition', 'then' and 'else'.",
            args.keypath,
        )

    condition = args.resolve(args.input["condition"], schema={"type": "boolean"})

    if condition:
        return args.resolve(args.input["then"])
    else:
        return args.resolve(args.input["else"])


@Function.new(resolve_input=False)
def let(args: FunctionArgs) -> Configuration:
    """Introduces a new "local" variable in the scope of the configuration.

    ``args.input`` should be a dictionary with two keys:

        - ``variables``: a dictionary mapping local variable names to their values
        - ``in``: the configuration in which the local variables are available

    """
    if not isinstance(args.input, dict):
        raise ResolutionError("Input to 'let' must be a dictionary.", args.keypath)

    if "in" not in args.input or "variables" not in args.input:
        raise ResolutionError(
            "Input to 'let' must be a dictionary with keys 'variables' and 'in'.",
            args.keypath,
        )

    if not isinstance(args.input["variables"], dict):
        raise ResolutionError(
            "The value of 'variables' in 'let' must be a dictionary.", args.keypath
        )

    local_variables = args.resolve(args.input["variables"], schema={"type": "any"})

    if not isinstance(local_variables, dict):
        raise ResolutionError(
            "The value of 'variables' in 'let' must be a dictionary.", args.keypath
        )

    return args.resolve(args.input["in"], local_variables=local_variables)


@Function.new(resolve_input=False)
def loop(args: FunctionArgs) -> Configuration:
    """Loops over a list of configurations.

    ``args.input`` should be a dictionary with three keys:

        - ``variable``: the name of the variable that will be assigned the
          value of each element in the list
        - ``over``: the list of configurations to loop over
        - ``in``: the configuration in which the variable is available. One
          copy will be made for each element in the list.

    """

    if (
        not isinstance(args.input, dict)
        or "variable" not in args.input
        or "over" not in args.input
        or "in" not in args.input
    ):
        raise ResolutionError(
            "Input to 'loop' must be a dictionary with keys 'variable', 'over' and 'in'.",
            args.keypath,
        )

    over = args.resolve(
        args.input["over"], schema={"type": "list", "element_schema": {"type": "any"}}
    )

    element_schema = args.schema["element_schema"]

    assert isinstance(args.input["variable"], str)

    if not isinstance(over, list):
        raise ResolutionError(
            "The value of 'over' in 'loop' must be a list.", args.keypath
        )

    result = []
    for element in over:
        local_variables = {args.input["variable"]: element}
        result.append(
            args.resolve(
                args.input["in"], local_variables=local_variables, schema=element_schema
            )
        )
    return result


def concatenate(args: FunctionArgs) -> ConfigurationList:
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


def zip_(args: FunctionArgs) -> ConfigurationList:
    """Zips lists together.

    ``args.input`` should be a list of lists.

    """
    if not isinstance(args.input, list) or not _all_elements_are_instances_of(
        args.input, list
    ):
        raise ResolutionError("Input to 'zip' must be a list of lists.", args.keypath)

    if len(args.input) == 0:
        raise ResolutionError(
            "Input to 'zip' must be a non-empty list of lists.", args.keypath
        )

    return [list(entry) for entry in zip(*args.input)]


@Function.new(resolve_input=False)
def filter_(args: FunctionArgs) -> ConfigurationList:
    """Filters a list.

    ``args.input`` should be a list of dictionaries with three keys:

        - ``iterable``: the list to filter
        - ``variable``: a string representing the name of the variable that will be
          assigned the value of each element in the list
        - ``condition``: a boolean expression that is evaluated

    """
    if (
        not isinstance(args.input, dict)
        or "iterable" not in args.input
        or "variable" not in args.input
        or "condition" not in args.input
    ):
        raise ResolutionError(
            "Input to 'filter' must be a dictionary with keys 'iterable', 'variable' and 'condition'.",
            args.keypath,
        )

    iterable = args.resolve(
        args.input["iterable"],
        schema={"type": "list", "element_schema": {"type": "any"}},
    )

    if not isinstance(iterable, list):
        raise ResolutionError(
            "The value of 'iterable' in 'filter' must be a list.", args.keypath
        )

    assert isinstance(args.input["variable"], str)

    result = []
    for element in iterable:
        local_variables = {args.input["variable"]: element}
        if args.resolve(
            args.input["condition"],
            local_variables=local_variables,
            schema={"type": "boolean"},
        ):
            result.append(element)

    return result


def range_(args: FunctionArgs) -> ConfigurationList:
    """Generates a list of numbers.

    ``args.input`` should be a dictionary with three keys, two of them optional:

        - ``start``: the start of the range (inclusive). Defaults to 0.
        - ``stop``: the end of the range (exclusive)
        - ``step``: the step between each element in the range. Defaults to 1.

    """
    if not isinstance(args.input, dict):
        raise ResolutionError("Input to 'range' must be a dictionary.", args.keypath)

    if "stop" not in args.input:
        raise ResolutionError(
            "Input to 'range' must be a dictionary with a key 'stop'.", args.keypath
        )

    start = args.input.get("start", 0)
    stop = args.input["stop"]
    step = args.input.get("step", 1)

    if set(args.input.keys()) - {"start", "stop", "step"}:
        raise ResolutionError(
            "Input to 'range' must be a dictionary with keys 'start', 'stop' and 'step'.",
            args.keypath,
        )

    if (
        not isinstance(start, int)
        or not isinstance(stop, int)
        or not isinstance(step, int)
    ):
        raise ResolutionError(
            "The values of 'start', 'stop' and 'step' in 'range' must be integers.",
            args.keypath,
        )

    return list(range(start, stop, step))


@Function.new(resolve_input=False)
def dict_from_items(args: FunctionArgs) -> ConfigurationDict:
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

    if not isinstance(input_, list):
        raise ResolutionError(
            "Input to 'dict_from_items' must be a list of dictionaries with keys 'key' and 'value'.",
            args.keypath,
        )

    dct = {}

    for item in input_:
        if not isinstance(item, dict) or set(item.keys()) != {"key", "value"}:
            raise ResolutionError(
                "Input to 'dict_from_items' must be a list of dictionaries with keys 'key' and 'value'.",
                args.keypath,
            )

        dct[item["key"]] = item["value"]

    return dct
