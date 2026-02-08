"""Core functions.

Some of these depend on the internal implementation details of _resolve and are
separated from _resolve.py for organizational clarity.

"""

from . import types as _types
from .exceptions import ResolutionError
from ._utils import deep_update
from ._internals import (
    ResolutionMode,
    _DictNode,
    _FunctionCallNode,
    _ListNode,
    _ValueNode,
    _ConcreteNode,
    make_node,
    _make_unresolved_container,
)


@_types.Function.new(resolve_input=False)
def _splice(args: _types.FunctionArgs) -> _ConcreteNode:
    """Copy a subtree from elsewhere in the configuration.

    ``args.input`` should be a string keypath (e.g., ``"foo.bar"``). The node at
    that keypath is resolved, then rebuilt under the destination's schema so that
    type conversion is applied according to the splice destination.

    """
    if not isinstance(args.input, str):
        raise ResolutionError("Input to 'splice' must be a string.", args.keypath)
    root = args._root_node
    assert isinstance(root, (_DictNode, _ListNode, _FunctionCallNode))
    try:
        source_node = root.get_keypath(args.input)
    except KeyError:
        raise ResolutionError(f"Keypath '{args.input}' does not exist.", args.keypath)

    # Resolve the source, then rebuild with the target schema so that type
    # conversion is applied according to the splice destination.
    spliced_data = source_node.resolve()
    return make_node(
        spliced_data,
        args.schema,
        args.resolution_context,
        parent=args._function_call_node,
        keypath=args.keypath,
        mode=ResolutionMode.STANDARD,
    )


@_types.Function.new(resolve_input=False)
def _raw(args: _types.FunctionArgs) -> _ConcreteNode:
    """Return the input without any string interpolation.

    Rebuilds the input as a node tree in RAW mode, so ``${...}`` references are
    preserved as literal text.

    """
    node = make_node(
        args.input,
        args.schema,
        args.resolution_context,
        keypath=args.keypath,
        mode=ResolutionMode.RAW,
    )
    return node


@_types.Function.new(resolve_input=False)
def _resolve(args: _types.FunctionArgs) -> _ConcreteNode:
    """Explicitly resolve the input with a single pass of interpolation.

    This is the default behavior, but is useful when nested inside a ``raw`` or
    ``fully_resolve`` block to override the inherited mode.

    """
    node = make_node(
        args.input,
        args.schema,
        args.resolution_context,
        parent=args._function_call_node,
        keypath=args.keypath,
        mode=ResolutionMode.STANDARD,
    )
    return node


@_types.Function.new(resolve_input=False)
def _fully_resolve(args: _types.FunctionArgs) -> _ConcreteNode:
    """Resolve the input with repeated interpolation until stable.

    Rebuilds the input in FULL mode, so ``${...}`` references are interpolated
    repeatedly until the string no longer changes.

    """
    node = make_node(
        args.input,
        args.schema,
        args.resolution_context,
        parent=args._function_call_node,
        keypath=args.keypath,
        mode=ResolutionMode.FULL,
    )
    return node


@_types.Function.new(resolve_input=False)
def _template(args: _types.FunctionArgs) -> _ConcreteNode:
    """Return a dict wrapping the input as a template that survives resolution.

    Builds ``{"__template__": <input>}`` in RAW mode so that ``${...}``
    references are preserved and the wrapper dict is not detected as a
    function call.

    """
    node = make_node(
        {"__template__": args.input},
        args.schema,
        args.resolution_context,
        keypath=args.keypath,
        mode=ResolutionMode.RAW,
    )
    return node


@_types.Function.new(resolve_input=False)
def _use(args: _types.FunctionArgs) -> _ConcreteNode:
    """Copy a template from elsewhere in the configuration, with optional overrides.

    ``args.input`` can be either:

    - a string keypath (e.g., ``"foo.bar"``), or
    - a dictionary with a ``"template"`` key (a keypath string) and an optional
      ``"overrides"`` key (a dictionary that is deep-merged on top of the
      resolved template).

    The referenced subtree is resolved, optionally merged with overrides, then
    rebuilt under the destination's schema.

    """
    # Parse input: string (simple) or dict (advanced with overrides).
    if isinstance(args.input, str):
        keypath_str = args.input
        overrides = None
    elif isinstance(args.input, dict):
        if "template" not in args.input:
            raise ResolutionError(
                "Dict input to 'use' must contain a 'template' key.", args.keypath
            )
        raw_template = args.input["template"]
        if not isinstance(raw_template, str):
            raise ResolutionError(
                "The 'template' value in 'use' must be a string.", args.keypath
            )
        keypath_str = raw_template
        overrides = args.input.get("overrides")
        if overrides is not None and not isinstance(overrides, dict):
            raise ResolutionError(
                "The 'overrides' value in 'use' must be a dictionary.", args.keypath
            )
        extra = set(args.input.keys()) - {"template", "overrides"}
        if extra:
            raise ResolutionError(f"Unexpected keys in 'use': {extra}.", args.keypath)
    else:
        raise ResolutionError(
            "Input to 'use' must be a string or a dictionary.", args.keypath
        )

    # Look up the node at the keypath and resolve it.
    root = args._root_node
    assert isinstance(root, (_DictNode, _ListNode, _FunctionCallNode))
    try:
        source_node = root.get_keypath(keypath_str)
    except KeyError:
        raise ResolutionError(f"Keypath '{keypath_str}' does not exist.", args.keypath)
    resolved = source_node.resolve()

    # The target must be a __template__ function call.
    if not isinstance(resolved, dict) or "__template__" not in resolved:
        raise ResolutionError(
            "The target of 'use' must be a '__template__' function call.",
            args.keypath,
        )

    # Unwrap the template contents.
    spliced_data = resolved["__template__"]

    # Apply overrides (deep merge).
    if overrides is not None:
        if not isinstance(spliced_data, dict):
            raise ResolutionError(
                "Overrides can only be applied when the template resolves to a dictionary.",
                args.keypath,
            )
        assert isinstance(overrides, dict)
        spliced_data = deep_update([spliced_data, overrides])

    # Resolve: build a STANDARD tree from the (possibly overridden) raw data.
    # The caller resolves this node, performing one pass of interpolation and
    # type conversion.
    node = make_node(
        spliced_data,
        args.schema,
        args.resolution_context,
        parent=args._function_call_node,
        keypath=args.keypath,
        mode=ResolutionMode.STANDARD,
    )
    return node


def _if(args: _types.FunctionArgs) -> _types.Configuration:
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


@_types.Function.new(resolve_input=False)
def _let(args: _types.FunctionArgs) -> _ConcreteNode:
    """Introduce local variables and/or references for use within a subtree.

    ``args.input`` should be a dictionary with an ``"in"`` key (the body) and
    one or both of:

    - ``"variables"``: a dictionary of values that are resolved and made
      available as local variables within the body.
    - ``"references"``: a dictionary mapping names to special targets
      (``"__this__"`` or ``"__previous__"``) that are exposed as unresolved
      containers, enabling self-referential or sibling-referential patterns.

    """
    if not isinstance(args.input, dict):
        raise ResolutionError("Input to 'let' must be a dictionary.", args.keypath)

    if "in" not in args.input:
        raise ResolutionError(
            "Input to 'let' must contain an 'in' key.",
            args.keypath,
        )

    has_variables = "variables" in args.input
    has_references = "references" in args.input

    if not has_variables and not has_references:
        raise ResolutionError(
            "Input to 'let' must contain 'variables' and/or 'references'.",
            args.keypath,
        )

    # Resolve regular variables.
    local_variables: dict = {}
    if has_variables:
        if not isinstance(args.input["variables"], dict):
            raise ResolutionError(
                "The value of 'variables' in 'let' must be a dictionary.",
                args.keypath,
            )
        resolved_vars = args.resolve(args.input["variables"], schema={"type": "any"})
        if not isinstance(resolved_vars, dict):
            raise ResolutionError(
                "The value of 'variables' in 'let' must be a dictionary.",
                args.keypath,
            )
        local_variables = resolved_vars

    # Build the "in" node without resolving it.
    fcn = args._function_call_node
    node = make_node(
        args.input["in"],
        args.schema,
        args.resolution_context,
        parent=fcn,
        keypath=args.keypath,
        local_variables=local_variables,
        mode=fcn.mode,
    )

    # Add references as local variables pointing to unresolved containers.
    if has_references:
        if not isinstance(args.input["references"], dict):
            raise ResolutionError(
                "The value of 'references' in 'let' must be a dictionary.",
                args.keypath,
            )
        for name, target in args.input["references"].items():
            if target == "__this__":
                if isinstance(node, _ValueNode):
                    raise ResolutionError(
                        "'__this__' cannot be used when 'in' is a scalar value.",
                        args.keypath,
                    )
                node.local_variables[name] = _make_unresolved_container(node)
            elif target == "__previous__":
                parent = fcn.parent
                if not isinstance(parent, _ListNode):
                    raise ResolutionError(
                        "'__previous__' can only be used inside a list.",
                        args.keypath,
                    )
                index = parent.children.index(fcn)
                if index == 0:
                    raise ResolutionError(
                        "'__previous__' cannot be used on the first element of a list.",
                        args.keypath,
                    )
                prev_node = parent.children[index - 1]
                if isinstance(prev_node, _ValueNode):
                    node.local_variables[name] = prev_node.resolve()
                else:
                    node.local_variables[name] = _make_unresolved_container(prev_node)

    return node


CORE_FUNCTIONS: _types.FunctionMapping = {
    "fully_resolve": _fully_resolve,
    "if": _if,
    "let": _let,
    "raw": _raw,
    "resolve": _resolve,
    "splice": _splice,
    "template": _template,
    "use": _use,
}
