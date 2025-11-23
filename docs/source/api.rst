Core API
========

.. module:: smartconfig
   :noindex:

The core functionality of `smartconfig` is exposed through two main functions:
:func:`resolve` for resolving configurations and :func:`validate_schema` for
checking the validity of schemas.

.. function:: resolve(...) -> Configuration

    Resolve a configuration by interpolating and parsing its entries.

    Parameters
    ----------
    cfg : :class:`types.Configuration`
        The "raw" configuration to resolve.
    schema : :class:`types.Schema`
        The schema describing the structure of the resolved configuration.
        See: :ref:`schemas`.
    converters : Mapping[str, Callable]
        A dictionary mapping value types (as strings) to converter functions.
        The converter functions should take the raw value (after interpolation)
        and convert it to the specified type.

        If this argument is not provided, the default converters in
        :data:`DEFAULT_CONVERTERS` are used. See :doc:`default_converters` for more information
        on the built-in converters. See :doc:`custom_converters` for how to define custom converters.
    functions : Mapping[str, Union[Callable, :class:`types.Function`]]
        A mapping of function names to functions. The functions should either be basic
        Python functions accepting an instance of :class:`types.FunctionArgs` as input
        and returning a :class:`types.Configuration`, or they should be
        :class:`smartconfig.types.Function` instances.

        If this argument is not provided, the
        default functions in :data:`DEFAULT_FUNCTIONS` are used. If it is ``None``, no
        functions are made available.
        See :doc:`default_functions` for more information on the built-in functions.
        See :doc:`custom_functions` for how to define custom functions.
    global_variables : Optional[Mapping[str, Any]]
        A dictionary of global variables to make available during string interpolation.
        If this is not provided, no global variables are available.

        Global variables are not interpolated or parsed. For this reason, they are
        mostly used to provide extra functions to the string interpolation
        engine. If you wish to provide external variables, it is suggested to
        include them in the configuration itself as shown in
        :ref:`recipes_external_variables`.
    inject_root_as : Optional[str]
        If this is not None, the root of the configuration tree is made
        available during string interpolation as a variable with this name.
        The root is passed as an :class:`types.UnresolvedDict`,
        :class:`types.UnresolvedList`, or
        :class:`types.UnresolvedFunctionCall`. Defaults to ``None``.

        It is suggested to avoid this and instead use the convention in
        :ref:`recipes_external_variables`.
    filters : Optional[Mapping[str, Callable]]
        A dictionary of Jinja2 filters to make available to templates. These will be
        added to Jinja2's set of default filters. If ``None``, no custom filters are
        provided. Defaults to ``None``.
    preserve_type : bool (default: False)
        If False, the return value of this function is a plain Python
        dictionary or list. If this is True, however, `smartconfig` will
        attempt to return an object of the same type as the input ``cfg``.
        This is most useful in cases where the input is of a custom mapping type
        (such as an ordered dictionary) that should be preserved in the output.
        See :ref:`type-preservation` for more information.
    check_for_function_call : :class:`types.FunctionCallChecker`
        A function that checks if a :class:`types.ConfigurationDict` represents a
        function call. It is given the configuration and the available functions. If it
        is determined to be a function call, it returns a 2-tuple of the
        :class:`types.Function` and the input to the function. If not, it
        returns None. If it is determined to be a malformed function call, it
        should raise a ``ValueError``.

        If this argument is not provided, a default implementation is used that
        assumes function calls are dictionaries with a single key of the form
        ``__<function_name>__``. If set to None, function calls are effectively
        disabled.

        See: :ref:`customizing-function-call-syntax` for more information.

    Raises
    ------
    :class:`exceptions.InvalidSchemaError`
        If the schema is not valid.
    :class:`exceptions.ResolutionError`
        If the configuration does not match the schema, if there is a circular
        reference, or there is some other issue with the configuration itself.


.. autofunction:: validate_schema
