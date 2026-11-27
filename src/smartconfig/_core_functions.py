"""Core functions.

These build node trees directly, so they depend on the internals in _internals.py.

"""

from . import types as _types
from .exceptions import ResolutionError, UnexpectedTemplateError
from ._utils import jinja_reserved_name_problem
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
    _view,
    _expand_use,
    _is_in_progress,
)


def _node_in_place(
    args: _types.FunctionArgs,
    cfg: _types.Configuration,
    mode: ResolutionMode,
    local_variables: dict | None = None,
) -> _ConcreteNode:
    """``cfg`` as a node in place of the call that ``args`` was given to.

    The node has the call's schema and keypath, and the call as its parent.
    smartconfig resolves the node that a function returns.

    """
    return make_node(
        cfg,
        args.schema,
        args.resolution_context,
        parent=args._function_call_node,
        keypath=args.keypath,
        local_variables=local_variables,
        mode=mode,
    )


def _template_in_place(
    args: _types.FunctionArgs,
    value: _types.Configuration,
    template_schema: _types.Schema,
) -> _TemplateNode:
    """A template of ``value`` in place of the call, as :func:`_node_in_place`."""
    return _TemplateNode(
        value,
        template_schema,
        args.keypath,
        args.resolution_context,
        parent=args._function_call_node,
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
    # if the root is a function call still being evaluated (this splice is in its
    # input or its output, however deeply), the configuration is that call's output
    # and has no keys yet. Looking the keypath up would evaluate the root again,
    # which would be reported as a circular reference. ${...} and __use__ skip the
    # root in this case too (see _Node._look_up_name)
    if isinstance(root, _FunctionCallNode) and _is_in_progress(root.evaluate):
        raise ResolutionError(
            f"Keypath '{args.input}' does not exist: the configuration is the output "
            "of the function call at its root, which is still being evaluated, so "
            "there is nothing to copy from yet.",
            args.keypath,
        )
    try:
        source_node = root.get_keypath(args.input)
    except KeyError:
        raise ResolutionError(f"Keypath '{args.input}' does not exist.", args.keypath)

    # Resolve the source, then rebuild with the target schema so that type
    # conversion is applied according to the splice destination. The rebuild is
    # in RAW mode because the data is already resolved: resolving it again would
    # interpolate a __raw__ value like "${b}" or evaluate a dict like
    # {"__splice__": "c"} that __raw__ produced.
    return _node_in_place(args, source_node.resolve(), ResolutionMode.RAW)


@_types.Function.new(resolve_input=False)
def _raw(args: _types.FunctionArgs) -> _ConcreteNode:
    """Return the input without any string interpolation.

    Rebuilds the input as a node tree in RAW mode, so ``${...}`` references are
    preserved as literal text. Unlike the other core functions, the node has no
    parent: nothing in RAW mode looks anything up.

    """
    return make_node(
        args.input,
        args.schema,
        args.resolution_context,
        keypath=args.keypath,
        mode=ResolutionMode.RAW,
    )


@_types.Function.new(resolve_input=False)
def _resolve(args: _types.FunctionArgs) -> _ConcreteNode:
    """Explicitly resolve the input with a single pass of interpolation.

    This is the default behavior, but is useful inside a ``fully_resolve`` block
    to switch back to a single pass. It has no effect inside ``raw``, where nothing
    is evaluated.

    """
    return _node_in_place(args, args.input, ResolutionMode.STANDARD)


@_types.Function.new(resolve_input=False)
def _fully_resolve(args: _types.FunctionArgs) -> _ConcreteNode:
    """Resolve the input with repeated interpolation until stable.

    Rebuilds the input in FULL mode, so ``${...}`` references are interpolated
    repeatedly until the string no longer changes.

    """
    return _node_in_place(args, args.input, ResolutionMode.FULL)


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

    return _template_in_place(args, args.input, template_schema)


@_types.Function.new(resolve_input=False)
def _use(args: _types.FunctionArgs) -> _ConcreteNode:
    """Copy a template from elsewhere in the configuration, with optional overrides.

    ``args.input`` can be either:

    - a string keypath (e.g., ``"foo.bar"``), or
    - a dictionary with a ``"template"`` key (a keypath string) and an optional
      ``"overrides"`` key (a dictionary that is deep-merged on top of the
      template as written).

    The template's value is copied as written, the overrides are merged into it,
    and the result is treated as if it had been written here:

    - on a template field, it is kept as written: the result is a Template with
      that field's inner schema and parameters;
    - on any other field, it is resolved under the field's schema.

    """
    spliced_data = _expand_use(args.input, args._function_call_node, args.keypath)

    if args.schema.get("type") == "template":
        # a template field: keep the copy as written
        return _template_in_place(args, spliced_data, args.schema)

    # any other field: build a tree from the (possibly overridden) value as
    # written, in the call's own mode, as __if__ and __let__ do, so that inside
    # __fully_resolve__ it is interpolated until stable, like a "${...}" reference
    # in the same place. (The mode is never RAW: inside __raw__, function calls
    # aren't evaluated.)
    return _node_in_place(args, spliced_data, args._function_call_node.mode)


# resolve_input=False: otherwise the whole input, both branches included, would be
# resolved before this function runs, so the branch not taken would be evaluated
# (and could fail), and the chosen branch would be resolved a second time.
@_types.Function.new(resolve_input=False)
def _if(args: _types.FunctionArgs) -> _ConcreteNode:
    """Evaluates configurations, conditionally.

    ``args.input`` should be a dictionary with three keys:

        - ``condition``: a boolean expression that is evaluated
        - ``then``: the configuration to use if the condition is true
        - ``else``: the configuration to use if the condition is false

    Only the condition and the chosen branch are evaluated. The branch is built
    as a node at the function's own keypath, so errors and templates inside it
    report the keypath of the ``__if__`` call.

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

    branch = args.input["then"] if condition else args.input["else"]

    # Return the branch as a node instead of resolving it here. When a function
    # returns a plain value, smartconfig resolves that value. That breaks a branch
    # like {"__raw__": "${b}"}: resolving it here would return the string "${b}",
    # and smartconfig would resolve that again, yielding the value of b when what
    # we wanted was the raw string "${b}". On the other hand, if we return a node
    # it is also resolved by smartconfig, but since we didn't resolve it here, it
    # is only resolved once in total.
    return _node_in_place(args, branch, args._function_call_node.mode)


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

    # an unknown key (a misspelling of "variables", say) would otherwise be ignored
    unknown = set(args.input) - {"variables", "references", "in"}
    if unknown:
        raise ResolutionError(
            f"Unknown key(s) in the input to 'let': {', '.join(sorted(unknown))}. "
            "Its keys are 'variables', 'references' and 'in'.",
            args.keypath,
        )

    # a name like true or self could never be referred to: ${ true } would be
    # Jinja's literal, silently, not the variable
    for section in ("variables", "references"):
        names = args.input.get(section)
        for name in names if isinstance(names, dict) else ():
            problem = jinja_reserved_name_problem(name)
            if problem is not None:
                raise ResolutionError(
                    f"Invalid name in '{section}' of 'let': {problem}", args.keypath
                )

    if "variables" not in args.input and "references" not in args.input:
        raise ResolutionError(
            "Input to 'let' must contain 'variables' and/or 'references'.",
            args.keypath,
        )

    # Resolve regular variables. They must be a dict both as written and once
    # resolved: a dict can be a function call that resolves to something else
    local_variables = args.input.get("variables", {})
    if isinstance(local_variables, dict):
        local_variables = args.resolve(local_variables, schema={"type": "any"})
    if not isinstance(local_variables, dict):
        raise ResolutionError(
            "The value of 'variables' in 'let' must be a dictionary.",
            args.keypath,
        )

    # Build the "in" node without resolving it.
    fcn = args._function_call_node
    node = _node_in_place(args, args.input["in"], fcn.mode, local_variables)

    # Add references as local variables pointing to unresolved containers.
    references = args.input.get("references", {})
    if not isinstance(references, dict):
        raise ResolutionError(
            "The value of 'references' in 'let' must be a dictionary.",
            args.keypath,
        )
    for name, target in references.items():
        if target == "__this__":
            if isinstance(node, (_ValueNode, _TemplateNode)):
                raise ResolutionError(
                    "'__this__' cannot be used when 'in' is a value or a template.",
                    args.keypath,
                )
            node.local_variables[name] = _make_unresolved_container(node)
        elif target == "__previous__":
            # the result of a call wrapping this one at the same keypath (an
            # __if__ or another __let__, say) becomes the list element, so the
            # element is the outermost of these calls
            element = fcn
            parent = fcn.parent
            while (
                isinstance(parent, _FunctionCallNode) and parent.keypath == fcn.keypath
            ):
                element = parent
                parent = parent.parent

            # if a call is still above us, this __let__ is in that call's input,
            # like the body of list.loop. That input is not a list, so there is
            # no previous element
            if isinstance(parent, _FunctionCallNode):
                raise ResolutionError(
                    "'__previous__' cannot be used in the input of a function "
                    "call, such as the body of list.loop.",
                    args.keypath,
                )
            if not isinstance(parent, _ListNode):
                raise ResolutionError(
                    "'__previous__' can only be used inside a list.",
                    args.keypath,
                )
            index = parent.children.index(element)
            if index == 0:
                raise ResolutionError(
                    "'__previous__' cannot be used on the first element of a list.",
                    args.keypath,
                )
            # _view evaluates a function call, so that prev is its result, not
            # the call itself (which would leak into strings as an object)
            node.local_variables[name] = _view(parent.children[index - 1])
        else:
            # an unknown target (a misspelling of "__previous__", say) would
            # otherwise leave the name undefined, with no error saying why
            raise ResolutionError(
                f"Unknown reference target {target!r} for '{name}' in 'let'. "
                "The targets are '__this__' and '__previous__'.",
                args.keypath,
            )

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
