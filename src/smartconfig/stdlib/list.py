"""List-related functions: concatenate, zip, range, loop, and filter."""

import itertools

from ..types import (
    Function,
    FunctionArgs,
    FunctionMapping,
    ConfigurationDict,
    ConfigurationList,
    Configuration,
)
from ..exceptions import ResolutionError
from .._utils import jinja_reserved_name_problem
from ._args import list_of, to_integer


def _variable(input_: ConfigurationDict, function: str, args: FunctionArgs) -> str:
    """The ``variable`` of ``list.loop`` or ``list.filter``: the name bound in its body.

    Raises
    ------
    ResolutionError
        If it is not a string, or is a name that Jinja reserves.

    """
    variable = input_["variable"]
    # a bare assert would give no keypath
    if not isinstance(variable, str):
        raise ResolutionError(
            f"The value of 'variable' in '{function}' must be a string.", args.keypath
        )

    # a name like true or self could never be referred to: ${ true } would be
    # Jinja's literal, silently, not the variable
    problem = jinja_reserved_name_problem(variable)
    if problem is not None:
        raise ResolutionError(
            f"Invalid 'variable' in '{function}': {problem}", args.keypath
        )
    return variable


@Function.new(resolve_output=False)
def concatenate(args: FunctionArgs) -> ConfigurationList:
    """Concatenates lists.

    ``args.input`` should be a list of lists.

    """
    return list(itertools.chain(*list_of(list, "lists", "list.concatenate", args)))


@Function.new(resolve_output=False)
def zip_(args: FunctionArgs) -> ConfigurationList:
    """Zips lists together.

    ``args.input`` should be a list of lists.

    """
    return [list(entry) for entry in zip(*list_of(list, "lists", "list.zip", args))]


def range_(args: FunctionArgs) -> ConfigurationList:
    """Generates a list of numbers.

    ``args.input`` should be a dictionary with three keys, two of them optional:

        - ``start``: the start of the range (inclusive). Defaults to 0.
        - ``stop``: the end of the range (exclusive)
        - ``step``: the step between each element in the range. Defaults to 1.

    """
    if not isinstance(args.input, dict):
        raise ResolutionError(
            "Input to 'list.range' must be a dictionary.", args.keypath
        )

    if "stop" not in args.input:
        raise ResolutionError(
            "Input to 'list.range' must be a dictionary with a key 'stop'.",
            args.keypath,
        )

    if set(args.input.keys()) - {"start", "stop", "step"}:
        raise ResolutionError(
            "Input to 'list.range' must be a dictionary with keys 'start', 'stop' and 'step'.",
            args.keypath,
        )

    # convert rather than check the type, so that a value written as "${ n }",
    # which interpolates to a string, is accepted
    start = to_integer(args.input.get("start", 0), "start", "list.range", args)
    stop = to_integer(args.input["stop"], "stop", "list.range", args)
    step = to_integer(args.input.get("step", 1), "step", "list.range", args)

    # range() raises a bare ValueError for a step of 0, with no keypath
    if step == 0:
        raise ResolutionError(
            "The value of 'step' in 'list.range' must not be 0.", args.keypath
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
            "Input to 'list.loop' must be a dictionary with keys 'variable', 'over' and 'in'.",
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

    variable = _variable(args.input, "list.loop", args)

    result = []
    for i, element in enumerate(over):
        local_variables = {variable: element}
        result.append(
            args.resolve(
                args.input["in"],
                local_variables=local_variables,
                schema=element_schema,
                # so that an error in the body says which element it was for
                relative_keypath=(str(i),),
            )
        )
    return result


@Function.new(resolve_input=False, resolve_output=False)
def filter_(args: FunctionArgs) -> ConfigurationList:
    """Filters a list.

    ``args.input`` should be a dictionary with three keys:

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
            "Input to 'list.filter' must be a dictionary with keys 'iterable', 'variable' and 'condition'.",
            args.keypath,
        )

    iterable = args.resolve(
        args.input["iterable"],
        schema={"type": "list", "element_schema": {"type": "any"}},
    )

    assert isinstance(iterable, list)

    variable = _variable(args.input, "list.filter", args)

    result = []
    for i, element in enumerate(iterable):
        local_variables = {variable: element}
        if args.resolve(
            args.input["condition"],
            local_variables=local_variables,
            schema={"type": "boolean"},
            # so that an error in the condition says which element it was for, as
            # in list.loop. The index is the element's place in the iterable: the
            # output has no place for an element whose condition failed
            relative_keypath=(str(i),),
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
