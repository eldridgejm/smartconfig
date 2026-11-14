"""Core functions.

Some of these depend on the internal implementation details of _resolve and are
separated from _resolve.py for organizational clarity.

"""

from . import types as _types
from .exceptions import ResolutionError, UnexpectedTemplateError
from ._internals import (
    ResolutionMode,
    _DictNode,
    _FunctionCallNode,
    _ListNode,
    _ValueNode,
    _TemplateNode,
    _ConcreteNode,
    make_node,
    _make_unresolved_container,
    _expand_use,
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
    """Defer the input: it resolves to a :class:`Template` of it, as written.

    What the Template is depends on the field's schema:

    - on a template field, the Template has that field's inner schema and
      parameters;
    - on a field of type ``any``, it has schema ``any`` and no parameters;
    - any other field is evaluated now, so the wrapper is an error.

    """
    schema_type = args.schema.get("type")

    if schema_type == "template":
        template_schema = args.schema
    elif schema_type == "any":
        template_schema = {
            "type": "template",
            "schema": {"type": "any"},
            "parameters": [],
        }
    else:
        raise UnexpectedTemplateError(
            "This field is not a template: it is evaluated now. "
            "Remove the __template__ wrapper.",
            args.keypath,
            None,
        )

    return _TemplateNode(
        args.input,
        template_schema,
        args.keypath,
        args.resolution_context,
        parent=args._function_call_node,
    )


@_types.Function.new(resolve_input=False)
def _use(args: _types.FunctionArgs) -> _ConcreteNode:
    """Copy a template from elsewhere in the configuration, with optional overrides.

    ``args.input`` can be either:

    - a string keypath (e.g., ``"foo.bar"``), or
    - a dictionary with a ``"template"`` key (a keypath string) and an optional
      ``"overrides"`` key (a dictionary that is deep-merged on top of the
      resolved template).

    The template's value is copied as written, the overrides are merged into it,
    and the result is treated as if it had been written here:

    - on a template field, it is kept as written: the result is a Template with
      that field's inner schema and parameters;
    - on any other field, it is resolved under the field's schema.

    """
    spliced_data = _expand_use(args.input, args._function_call_node, args.keypath)

    if args.schema.get("type") == "template":
        # a template field: keep the copy as written
        return _TemplateNode(
            spliced_data,
            args.schema,
            args.keypath,
            args.resolution_context,
            parent=args._function_call_node,
        )

    # any other field: build a STANDARD tree from the (possibly overridden) value
    # as written. The caller resolves this node, performing one pass of
    # interpolation and type conversion.
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
                if isinstance(node, (_ValueNode, _TemplateNode)):
                    raise ResolutionError(
                        "'__this__' cannot be used when 'in' is a value or a template.",
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
                if isinstance(prev_node, (_ValueNode, _TemplateNode)):
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
