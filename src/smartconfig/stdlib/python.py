"""The python function, which runs a string as the body of a Python function.

The function runs whatever code a configuration contains, so it is not one of the
default functions: a configuration can use it only if it is passed to
:func:`smartconfig.resolve` explicitly.

"""

import textwrap

from ..types import Configuration, Function, FunctionArgs
from ..exceptions import ResolutionError, _join_dotted


# the name of the function that the body is placed in
_BODY_FUNCTION_NAME = "__smartconfig_python_body__"


# the input isn't resolved, since interpolation would rewrite anything in the code
# that looks like a ${...} or {{ ... }}. The output isn't resolved either: it is
# usually made from values that are already resolved, such as those read from
# args.root, and resolving them again could change them (undoing a __raw__, say)
@Function.new(resolve_input=False, resolve_output=False)
def python(args: FunctionArgs) -> Configuration:
    """Run ``args.input`` as the body of a function of ``args``, returning its result.

    ``args.input`` should be a string of Python code, such as ``"return 1 + 1"``. It
    is run as the body of a function whose one parameter is ``args``, so it can read
    other values in the configuration with ``args.root``.

    Raises
    ------
    ResolutionError
        If the input is not a string, is not valid Python, or raises an exception.
        A ``ResolutionError`` raised while the body runs (by ``args.root``, say)
        is passed on unchanged, with its own keypath.

    """
    if not isinstance(args.input, str):
        raise ResolutionError(
            f"Input to 'python' must be a string, got {type(args.input).__name__}.",
            args.keypath,
        )

    # an empty body would be reported as a syntax error in the "def" line added
    # below, which isn't in the configuration
    if not args.input.strip():
        raise ResolutionError("Input to 'python' must not be empty.", args.keypath)

    # dedented first, so that a body written indented (in a Python string, say)
    # isn't indented twice
    body = textwrap.indent(textwrap.dedent(args.input), "    ")
    source = f"def {_BODY_FUNCTION_NAME}(args):\n{body}"

    # the file name shows up in tracebacks, so that an error in the body can be
    # traced back to where it is in the configuration
    filename = f"<python at {_join_dotted(args.keypath)}>"
    try:
        code = compile(source, filename, "exec")
    except SyntaxError as exc:
        # the line number counts the "def" line added above, so it is one more
        # than the line in the body
        line = (exc.lineno or 1) - 1
        raise ResolutionError(
            f"Invalid Python in line {line}: {exc.msg}.", args.keypath
        ) from exc

    namespace: dict = {}
    exec(code, namespace)
    body_function = namespace[_BODY_FUNCTION_NAME]

    try:
        return body_function(args)
    except ResolutionError:
        raise
    except Exception as exc:
        raise ResolutionError(f"{type(exc).__name__}: {exc}", args.keypath) from exc
