Resolution
==========

A configuration is resolved using the :func:`smartconfig.resolve` function.

.. module:: smartconfig

.. function:: resolve

    Resolve a configuration by interpolating and parsing its entries.

    The configuration can be a dictionary, list, or a non-container type; resolution
    will be done recursively. In any case, the provided schema must match the type of
    the configuration; for example, if the configuration is a dictionary, the schema
    must be a dict schema.


    Parameters
    ----------
    cfg : Configuration
        The "raw" configuration to resolve.
    schema : Schema
        The schema describing the structure of the resolved configuration.
    parsers : Mapping[str, Callable]
        A dictionary mapping value types to parser functions. The parser functions
        should take the raw value (after interpolation) and convert it to the specified
        type. If this is not provided, the default parsers are used.
    functions
        A mapping of function names to functions. The functions should either be basic
        Python functions accepting an instance of FunctionArgs as input and returning
        a Configuration, or they should be :class:`smartconfig.types.Function` instances. If this is not
        provided, the default functions are used.
    global_variables : Optional[Mapping[str, Any]]
        A dictionary of global variables to make available to Jinja2 templates. If this
        is not provided, no global variables are available.
    inject_root_as : Optional[str]
        If this is not None, the root of the configuration tree is made available to
        Jinja2 templates as an UnresolvedDict, UnresolvedList, or UnresolvedFunctionCall
        by injecting it into the template variables as the value of this key.
    filters : Optional[Mapping[str, Callable]]
        A dictionary of Jinja2 filters to make available to templates. Will be added to
        the default filters.
    schema_validator : Callable[[Schema], None]
        A function to validate the schema. If this is not provided, the default schema
        validator is used (:func:`smartconfig.validate_schema`).
    preserve_type : bool (default: False)
        If False, the return value of this function is a plain Python dictionary or
        list. If this is True, however, the return type will be the same as the type of
        cfg. See below for details.

    Raises
    ------
    InvalidSchemaError
        If the schema is not valid.
    ResolutionError
        If the configuration does not match the schema, if there is a circular
        reference, or there is some other issue with the configuration itself.

Default Parsers
---------------

Default parsers are provided which attempt to convert input values to the specified
types. They are:

- "integer": :func:`smartconfig.parsers.arithmetic` with type `int`
- "float": :func:`smartconfig.parsers.arithmetic` with type `float`
- "string": n/a.
- "boolean": :func:`smartconfig.parsers.logic`
- "date": :func:`smartconfig.parsers.smartdate`
- "datetime": :func:`smartconfig.parsers.smartdatetime`

These parsers provide "smart" behavior, allowing values to be expressed in a variety
of formats. They can be overridden by providing a dictionary of parsers to
`override_parsers`.

Default Functions
-----------------

Default functions are provided that allow for basic manipulation of the
configuration. They are:

- "raw": :func:`smartconfig.functions.raw`
- "splice": :func:`smartconfig.functions.splice`
- "update_shallow": :func:`smartconfig.functions.update_shallow`
- "update": :func:`smartconfig.functions.update`
- "concatenate": :func:`smartconfig.functions.concatenate`

This function uses the `jinja2` template engine for interpolation. This means that
many powerful `Jinja2` features can be used. For example, `Jinja2` supports a
ternary operator, so dictionaries can contain expressions like the following:"

.. code-block:: python

    {
        'x': 10,
        'y': 3,
        'z': '${ this.x if this.x > this.y else this.y }'
    }

Jinja2 filters are functions that can be applied during string interpolation. Jinja
provides many built-in filters, but custom filters can also be provided via the
`filters` keyword argument.

Global variables can be provided to Jinja2 templates through the `global_variables`
keyword argument. If a global variable's name clashes with a key in the
configuration, the value from the configuration takes precedence. Typically, this
manifests as a circular reference.

Type Preservation
-----------------

Typically, the input to :func:`resolve` will be a plain Python object (e.g., a ``dict``
or a ``list``). Sometimes, however, it may be another mapping type that behaves like a
`dict`, but has some additional functionality. One example is the `ruamel` package which
is capable of round-tripping yaml, comments and all. To accomplish this, ruamel produces
a dict-like object which stores the comments internally. If we resolve this dict-like
object with :code:`preserve_type = False`, then we'll lose these comments; therefore, we
should use :code:`preserve_type = True`. At present, type preservation is done by
constructing the resolved output as normal, but then making a deep copy of `cfg` and
recursively copying each leaf value into this deep copy. Therefore, there is a
performance cost.
