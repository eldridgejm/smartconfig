"""List-related functions: concatenate, zip, range, loop, and filter."""

import itertools
import typing

from ..types import (
    Function,
    FunctionArgs,
    FunctionMapping,
    ConfigurationList,
    Configuration,
)
from ..exceptions import ResolutionError
from ._integers import to_integer


# helpers ==============================================================================


def _all_elements_are_instances_of(container, type_):
    """Check if all elements in the container are instances of the given type."""
    return all(isinstance(element, type_) for element in container)


# functions ============================================================================


@Function.new(resolve_output=False)
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


@Function.new(resolve_output=False)
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

    # convert rather than check the type, so that a value written as "${ n }",
    # which interpolates to a string, is accepted
    start = to_integer(start, "start", "range", args)
    stop = to_integer(stop, "stop", "range", args)
    step = to_integer(step, "step", "range", args)

    # range() raises a bare ValueError for a step of 0, with no keypath
    if step == 0:
        raise ResolutionError(
            "The value of 'step' in 'range' must not be 0.", args.keypath
        )

    return list(range(start, stop, step))


@Function.new(resolve_input=False, resolve_output=False)
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

    # an "any" schema has no element_schema; resolve the elements under "any"
    # too. Under any other non-list schema, the list this returns is reported as
    # the wrong shape, as usual
    element_schema = args.schema.get("element_schema", {"type": "any"})

    assert isinstance(over, list)

    # the variable is a name, bound in the body; a bare assert would give no keypath
    if not isinstance(args.input["variable"], str):
        raise ResolutionError(
            "The value of 'variable' in 'loop' must be a string.", args.keypath
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


@Function.new(resolve_input=False, resolve_output=False)
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

    assert isinstance(iterable, list)
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


LIST_FUNCTIONS: FunctionMapping = {
    "concatenate": concatenate,
    "filter": filter_,
    "loop": loop,
    "range": range_,
    "zip": zip_,
}
