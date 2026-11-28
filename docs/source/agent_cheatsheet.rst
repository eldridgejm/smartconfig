Agent Cheat Sheet
=================

.. testsetup::

    import smartconfig
    from pprint import pprint

This page is intended for AI agents. It summarizes the configuration language
and schemas on one page, so that an agent can read all of it before editing a
smartconfig configuration or writing code that calls smartconfig. One of the
quickest ways to get started with smartconfig is to point your agent at this
page (see "Telling an agent about smartconfig" at the end). Each section ends
with the name of the page that covers its topic in full. Those pages are in the
same directory as this one (``smartconfig/docs/`` in the installed package) and
at https://eldridgejm.github.io/smartconfig/.

The examples are Python dicts. A configuration can come from any source (JSON,
YAML, TOML, Python, ...) that gives dicts, lists and values.
They are resolved with ``smartconfig.resolve(config, schema)``, and most use
the schema ``{"type": "any"}``, which accepts anything and converts nothing.


Interpolation: ``${...}``
-------------------------

A string containing ``${ expr }`` is a Jinja2 template whose variable
delimiters are ``${`` and ``}``. Jinja's usual ``{{ ... }}`` is **not**
interpolated: it is kept as literal text. ``{% ... %}`` blocks and
``{# ... #}`` comments work as in Jinja.

.. testcode::

    config = {
        "course": {"name": "DSC 40B", "topics": ["Sorting", "Graphs"]},
        "n": 3,
        "title": "Welcome to ${ course.name }!",
        "first": "${ course.topics[0] } or ${ course.topics.1 }",
        "math": "${ n * 2 + 1 }",
        "filters": "${ course.topics | join(', ') | upper }",
        "cond": "${ 'many' if n > 2 else 'few' }",
        "loop": "{% for t in course.topics %}${ loop.index }. ${ t } {% endfor %}",
        "jinja": "{{ n }}",
    }
    pprint(smartconfig.resolve(config, {"type": "any"}))

.. testoutput::

    {'cond': 'many',
     'course': {'name': 'DSC 40B', 'topics': ['Sorting', 'Graphs']},
     'filters': 'SORTING, GRAPHS',
     'first': 'Sorting or Graphs',
     'jinja': '{{ n }}',
     'loop': '1. Sorting 2. Graphs ',
     'math': '7',
     'n': 3,
     'title': 'Welcome to DSC 40B!'}

**Names and keypaths.** A name in ``${...}`` is looked up in this order:

1. local variables (from ``__let__``, ``__list.loop__``, ``__list.filter__``);
2. the configuration, **from its root**. Inside a template, the root is the
   template's own value;
3. template parameters (inside a template being evaluated);
4. global variables passed with ``resolve(..., global_variables={...})``, and
   the root itself if ``resolve(..., inject_root_as="name")`` was given.

Names are never relative to the string's position: in
``{"a": {"x": 1, "y": "${ x }"}}``, ``x`` is undefined; write ``${ a.x }``.
Walk into dicts with ``.key`` or ``["key"]`` and into lists with ``[0]`` or
``.0``. A key that is not an identifier (``my-key``) needs subscripting on its
container: ``${ parent["my-key"] }`` (at the top level, only through
``inject_root_as``).

**What a reference gives.** The referenced value is resolved first, on
demand, in any order, under its own schema, so a ``date`` field arrives as a
``datetime.date`` (``${ start.year }`` works) but the same string in an ``any``
field is still a string. A cycle (``a`` uses ``b`` uses ``a``) is an error.

**The result is always a string**, which is then converted to the field's
type (see Converters below): ``"${ n + 1 }"`` is ``4`` in an ``integer``
field and ``"4"`` in a ``string`` or ``any`` field.

**Available inside** ``${...}``: Jinja expressions (arithmetic, comparisons,
``and``/``or``/``not``, ``x if c else y``, literals, list/dict literals),
methods of the values (``s.upper()``), Jinja's built-in filters
(``length``, ``join``, ``default``, ``upper``, ``round``, ...) and globals
(``range``, ``dict``, ``namespace``, ...), plus whatever the program passes as
``global_variables`` and ``filters``. **Not available**: Python builtins
(``len`` is undefined; use ``| length``), imports, and anything the program
didn't provide.

**Errors and escapes.**

- Inserting ``None``, a dict, a list or a template into a string is an error.
  Insert one key or element, use a filter (``| join``), copy the whole value
  with ``__splice__``, or give a default as in ``${ x or '' }``.
- An undefined name is an ``UndefinedNameError`` that lists the names
  available.
- A literal ``${`` is ``${ '${' }``; likewise ``${ '{%' }`` and
  ``${ '{#' }``. ``{% raw %}...{% endraw %}`` keeps a stretch as written, and
  ``__raw__`` a whole value. ``$${ x }`` is not an escape: it is ``$`` and then
  the value, as in a price.
- A string with none of ``${``, ``{%``, ``{#`` is kept exactly as written.

Full details: resolution.rst and resolution_in_detail.rst.


Function calls
--------------

A function call is a dict with exactly **one** key, ``"__name__"``, whose value
is the function's input: ``{"__if__": {...}}``, ``{"__list.loop__": {...}}``.
Any dict with a key of the form ``__name__`` is read as a call, so it may not
have other keys, and the name must be a function that the program provides
(``Unknown function`` otherwise). The call is evaluated, then its result is
resolved under the field's schema like any other value. Functions with a dotted
name are written with the dot: ``__datetime.parse__``. In TOML, quote such a
key (``"__list.loop__"``), since a bare dotted key makes nested tables.

The functions below are the defaults (``smartconfig.DEFAULT_FUNCTIONS``).
These are the only names that exist; there is no ``__concat__``, ``__merge__``,
``__env__`` or ``__now__``, for example. A program may add its own functions
(custom_functions.rst) or remove all of them (``functions=None``).

Core functions
~~~~~~~~~~~~~~

``__if__``: ``{"condition": <bool>, "then": <cfg>, "else": <cfg>}``
    All three keys are required, and no others are allowed. Only the chosen
    branch is evaluated.

``__let__``: ``{"variables": {<name>: <cfg>, ...}, "references": {<name>: "__this__" | "__previous__"}, "in": <cfg>}``
    ``in`` is required, with ``variables``, ``references`` or both. Variables are
    resolved and visible by name inside ``in``. ``"__this__"`` names the ``in``
    value itself (not allowed when ``in`` is a single value), so its keys can
    refer to each other; ``"__previous__"`` names the previous element of the
    enclosing list (not on the first element, nor in a function's input such as
    a ``list.loop`` body).

``__raw__``: ``<cfg>``
    The input as written: no interpolation, no function calls. It is still
    converted to the field's type.

``__resolve__``: ``<cfg>``
    A single pass of interpolation (the default). Only useful inside
    ``__fully_resolve__``.

``__fully_resolve__``: ``<cfg>``
    Interpolates repeatedly until the string stops changing, for a reference to
    a string that itself contains ``${...}``.

``__splice__``: ``"<keypath>"``
    A copy of the resolved value at the keypath, such as ``"a.b"`` or
    ``"a.0"``, always looked up from the root (local and global variables are not
    searched). The copy is converted under the destination's schema. Use it to
    copy a dict, a list or ``None``, which ``${...}`` can't insert.

``__template__``: ``<cfg>``
    Keeps the value as written and makes it a ``smartconfig.types.Template``,
    evaluated later. Allowed only on a field whose schema type is ``template`` or
    ``any``; anywhere else it is an ``UnexpectedTemplateError``.

``__use__``: ``"<keypath>"`` or ``{"template": "<keypath>", "overrides": {...}}``
    Pastes a copy of a template's value, as written, with ``overrides``
    deep-merged into it, and then treats it as if it had been written here: its
    ``${...}`` names are looked up from here. The target must be a template, and
    is looked up as ``${...}`` would look it up (so it may be a global variable).
    On a template field, the paste is kept as a template.

.. testcode::

    config = {
        "n": 3,
        "if": {"__if__": {"condition": "${ n > 2 }", "then": "big", "else": "small"}},
        "let": {"__let__": {"variables": {"m": 10}, "in": "${ m + n }"}},
        "this": {"__let__": {"references": {"me": "__this__"},
                             "in": {"a": 1, "b": "${ me.a + 1 }"}}},
        "raw": {"__raw__": "${ n }"},
        "splice": {"__splice__": "this"},
        "greeting": {"__template__": {"text": "Hi ${ who }", "n": "${ n }"}},
        "used": {"__use__": {"template": "greeting", "overrides": {"n": 0}}},
        "who": "Ada",
    }
    pprint(smartconfig.resolve(config, {"type": "any"}))

.. testoutput::

    {'greeting': Template(at "greeting", parameters: none),
     'if': 'big',
     'let': '13',
     'n': 3,
     'raw': '${ n }',
     'splice': {'a': 1, 'b': '2'},
     'this': {'a': 1, 'b': '2'},
     'used': {'n': 0, 'text': 'Hi Ada'},
     'who': 'Ada'}

``__previous__`` numbers the elements of a list, each from the one before:

.. testcode::

    config = [
        {"week": 1},
        {"__let__": {"references": {"prev": "__previous__"},
                     "in": {"week": "${ prev.week + 1 }"}}},
    ]
    schema = {"type": "list", "element_schema": {
        "type": "dict", "required_keys": {"week": {"type": "integer"}}}}
    pprint(smartconfig.resolve(config, schema))

.. testoutput::

    [{'week': 1}, {'week': 2}]

``__fully_resolve__``: with ``"tpl": {"__raw__": "hi ${ name }"}``,
``{"__fully_resolve__": "${ tpl }"}`` is ``"hi Ada"`` where a plain
``"${ tpl }"`` is ``"hi ${ name }"``.

List functions
~~~~~~~~~~~~~~

``__list.loop__``: ``{"variable": "<name>", "over": <list>, "in": <cfg>}``
    One copy of ``in`` per element of ``over``, with the element bound to
    ``variable``. Each copy is resolved under the list's element schema.

``__list.filter__``: ``{"iterable": <list>, "variable": "<name>", "condition": <bool>}``
    The elements for which ``condition`` is true.

``__list.range__``: ``{"stop": <int>, "start": <int>, "step": <int>}``
    Like Python's ``range``. ``stop`` is required; ``start`` defaults to 0 and
    ``step`` to 1 (and may not be 0). Strings like ``"${ n }"`` are accepted.

``__list.zip__``: ``[<list>, <list>, ...]``
    Like Python's ``zip``, as a list of lists. The input must be non-empty.

``__list.concatenate__``: ``[<list>, <list>, ...]``
    The lists joined end to end. The input must be non-empty.

Dict functions
~~~~~~~~~~~~~~

``__dict.update__``: ``[<dict>, <dict>, ...]``
    Deep merge: later dicts win, and nested dicts are merged recursively.
    Non-empty.

``__dict.update_shallow__``: ``[<dict>, <dict>, ...]``
    Like ``dict.update``, but a nested dict replaces the earlier one.

``__dict.from_items__``: ``[{"key": "<str>", "value": <cfg>}, ...]``
    A dict built from key/value pairs. Each key must be a string.

.. testcode::

    config = {
        "loop": {"__list.loop__": {"variable": "i", "over": [1, 2, 3], "in": "w${ i }"}},
        "filter": {"__list.filter__": {"iterable": [1, 2, 3, 4], "variable": "x",
                                       "condition": "${ x % 2 == 0 }"}},
        "range": {"__list.range__": {"start": 1, "stop": 10, "step": 4}},
        "zip": {"__list.zip__": [[1, 2], ["a", "b"]]},
        "concatenate": {"__list.concatenate__": [[1], [2, 3]]},
        "update": {"__dict.update__": [{"a": {"x": 1}}, {"a": {"y": 2}}]},
        "update_shallow": {"__dict.update_shallow__": [{"a": {"x": 1}}, {"a": {"y": 2}}]},
        "from_items": {"__dict.from_items__": [{"key": "k", "value": 1}]},
    }
    pprint(smartconfig.resolve(config, {"type": "any"}))

.. testoutput::

    {'concatenate': [1, 2, 3],
     'filter': [2, 4],
     'from_items': {'k': 1},
     'loop': ['w1', 'w2', 'w3'],
     'range': [1, 5, 9],
     'update': {'a': {'x': 1, 'y': 2}},
     'update_shallow': {'a': {'y': 2}},
     'zip': [[1, 'a'], [2, 'b']]}

Datetime functions
~~~~~~~~~~~~~~~~~~

A reference date is an ISO string (``"2025-09-01"``, ``"2025-09-01 23:59"``), a
``date`` or a ``datetime``. The result is a ``date`` unless something gives it a
time (a datetime reference, an offset in hours/minutes/seconds, ``at HH:MM``,
or ``datetime.at``); midnight is never assumed.

``__datetime.parse__``: ``"<phrase>"``
    One of: an ISO date or datetime; ``"<offset> after|before <date>"``, with
    the offset like ``"3 days"`` or ``"1 week, 2 days"``; or
    ``"first <weekdays> after|before <date>"``, with weekdays like ``"monday"``,
    ``"monday, friday"`` or ``"monday or friday"``. Any form may end with
    ``" at HH:MM"`` or ``" at HH:MM:SS"``. Case-insensitive.

``__datetime.offset__``: ``{"after" | "before": <date>, "by": <offset>, "skip": [<date>, ...]}``
    Exactly one of ``after``/``before``, and ``by``, are required; ``by`` is a
    string as above or a dict like ``{"weeks": 1, "days": 2}``. Units:
    ``weeks``, ``days``, ``hours``, ``minutes``, ``seconds``, each at most once.
    A result on a ``skip`` date moves on, a day at a time, in the same direction.

``__datetime.first__``: ``{"weekday": <names>, "after" | "before": <date>, "skip": [<date>, ...]}``
    The first of the given weekdays strictly after (or before) the date: the
    first Monday after a Monday is a week later. ``weekday`` is a string as
    above or a list of names. Names are full day names (``"mon"`` is an error).

``__datetime.at__``: ``{"date": <date>, "time": "HH:MM[:SS]"}``
    The date at that time, as a datetime. Both keys are required.

Unknown keys are an error in ``offset``, ``first`` and ``at``.

.. testcode::

    config = {
        "start": "2025-09-01",
        "parse": {"__datetime.parse__": "first tuesday after ${ start } at 9:00"},
        "offset": {"__datetime.offset__": {"after": "${ start }", "by": "1 week",
                                           "skip": ["2025-09-08"]}},
        "first": {"__datetime.first__": {"weekday": ["monday", "friday"],
                                         "after": "${ start }"}},
        "at": {"__datetime.at__": {"date": "${ start }", "time": "23:59"}},
    }
    pprint(smartconfig.resolve(config, {"type": "any"}))

.. testoutput::

    {'at': datetime.datetime(2025, 9, 1, 23, 59),
     'first': datetime.date(2025, 9, 5),
     'offset': datetime.date(2025, 9, 9),
     'parse': datetime.datetime(2025, 9, 2, 9, 0),
     'start': '2025-09-01'}

``__python__`` (opt-in)
~~~~~~~~~~~~~~~~~~~~~~~

``{"__python__": "<code>"}`` runs the string as the body of a Python function
and uses what it returns. It is **not** a default function: it works only if
the program adds ``smartconfig.stdlib.python.python`` to ``functions``, since it
runs arbitrary code. See inline_python.rst.

Full details: default_functions.rst.


Schemas
-------

A schema is a dict with a ``"type"``. ``resolve`` validates it and raises
``InvalidSchemaError`` for an unknown or missing key.

.. code:: text

    {"type": "dict",
     ["required_keys": {<key>: <schema>, ...}],
     ["optional_keys": {<key>: <schema, may have "default">, ...}],
     ["extra_keys_schema": <schema>],
     ["nullable": bool]}

    {"type": "list", "element_schema": <schema>, ["nullable": bool]}

    {"type": "template", "schema": <schema>, "parameters": [<name>, ...],
     ["nullable": bool]}

    {"type": "any", ["nullable": bool]}

    {"type": <converter name>, ["nullable": bool]}
        by default: "string", "integer", "float", "boolean", "date", "datetime"

Those are all the keys there are. In detail:

- ``required_keys`` must be present; ``optional_keys`` may be missing. A key
  may not be in both. A key in neither is an error ("unexpected extra key")
  unless ``extra_keys_schema`` is given, which is then the schema of every other
  key. A dict schema with none of the three accepts only ``{}``.
- ``default`` is allowed only on a schema directly under ``optional_keys``. A
  missing optional key without a default is left out of the result. A default
  is resolved like a written value (``"${ x + 1 }"`` works), and a dict default
  gets its own keys' defaults.
- ``nullable``: whether ``None`` is allowed. It defaults to ``False``, except
  for ``any``, which defaults to ``True``. It must be a real ``bool``.
- ``element_schema`` is required for a list. It may not have a default.
- ``any`` accepts anything and converts nothing (``"${ n }"`` stays a string).
  Function calls and ``${...}`` inside it are still evaluated.
- ``template``: the field's value must be written as
  ``{"__template__": <value>}`` (or come from ``__use__``), and resolves to a
  ``smartconfig.types.Template``. ``schema`` describes the evaluated value;
  ``parameters`` lists the names that ``Template.evaluate({...})`` must be given,
  exactly. A parameter may not share a name with a top-level key of the
  template's value. A template sees nothing of the rest of the configuration, only
  its own value, its parameters and the global variables. The default of a
  template field is written without the ``__template__`` wrapper. When the
  configuration is resolved, the template's structure (keys, nulls) is checked
  and its function names must exist, but nothing in it is evaluated.
- Anywhere a schema goes, a Python function ``(raw_value, keypath) -> schema``
  (a *dynamic schema*) may be given instead.

.. testcode::

    schema = {
        "type": "dict",
        "required_keys": {"name": {"type": "string"}},
        "optional_keys": {
            "tags": {"type": "list", "element_schema": {"type": "string"}, "default": []},
            "email": {"type": "string", "nullable": True},
            "page": {"type": "template", "schema": {"type": "string"},
                     "parameters": ["hw"], "default": "Homework ${ hw }"},
        },
    }
    result = smartconfig.resolve({"name": "DSC 40B", "email": None}, schema)
    pprint(result)
    pprint(result["page"].evaluate({"hw": 3}))

.. testoutput::

    {'email': None,
     'name': 'DSC 40B',
     'page': Template(at "page", parameters: hw),
     'tags': []}
    'Homework 3'

**Prototypes.** A dict schema can be written as a dataclass-like class instead:
subclass ``smartconfig.Prototype``, and ``resolve(config, MyClass)`` returns an
instance. Fields map to schemas by type hint (``str``, ``int``, ``float``,
``bool``, ``datetime.date``, ``datetime.datetime``, ``Any``, ``T | None``,
``list[T]``, ``dict[str, T]``, another Prototype). A field with a default is
optional, and a field typed ``... | None`` is nullable. Other schemas go in
``Annotated[T, smartconfig.prototypes.schema({...})]`` or, for a template
field, ``Annotated[Template, smartconfig.prototypes.template(schema,
parameters)]``. ``class C(Prototype, extra_keys=str)`` allows extra keys, kept
in ``instance.extra_keys``. See prototypes.rst.

Full details: schemas.rst.


Converters
----------

After interpolation, a value is converted by the converter named by its
schema's type. The defaults (``smartconfig.DEFAULT_CONVERTERS``):

=============  =======================  ============================================
Type           Result                   Accepts
=============  =======================  ============================================
``string``     ``str``                  anything, through ``str()`` (``5`` becomes
                                        ``"5"``)
``integer``    ``int``                  ints, whole floats (``3.0``), whole-number
                                        strings (``"42"``). Not bools, ``4.5``,
                                        ``"3.0"``
``float``      ``float``                floats, ints, numeric strings (``"4.5"``,
                                        ``"inf"``). Not bools
``boolean``    ``bool``                 ``True``/``False`` and exactly
                                        ``"True"``/``"False"``. Not ``"true"``,
                                        ``"yes"``, ``1``
``date``       ``datetime.date``        ISO date or datetime strings (the time is
                                        dropped), dates, datetimes
``datetime``   ``datetime.datetime``    ISO datetime strings and datetimes. Not a
                                        date-only string or a ``date``
``any``        unchanged                anything; no conversion
=============  =======================  ============================================

Converters don't evaluate expressions: ``"2 + 2"`` is not an integer, while
``"${ 2 + 2 }"`` is. A ``${...}`` that yields ``True`` gives the string
``"True"``, which a ``boolean`` field accepts. A program can add converters, and
each is a new schema type (custom_converters.rst). Full details:
default_converters.rst.


Reserved names
--------------

- Jinja reads ``true``, ``True``, ``false``, ``False``, ``none`` and ``None`` as
  literals, ``not`` as an operator and ``self`` as the template, so
  ``${ true }`` is always ``True`` even if the configuration has a key
  ``true``. Such a key is still reachable through its container
  (``${ flags.true }``) or through ``inject_root_as`` (``${ root["true"] }``).
  These names are errors wherever a name is introduced: a ``__let__`` variable
  or reference, the ``variable`` of ``__list.loop__``/``__list.filter__``, a
  template parameter, a global variable or ``inject_root_as``.
- Inside ``{% for %}``, ``loop`` is Jinja's loop variable.
- Any key of the form ``__name__`` is a function call.
- ``__this__`` and ``__previous__`` are the reference targets of ``__let__``.
- A Prototype may not have a field named ``extra_keys``.


Common mistakes
---------------

- Writing ``{{ x }}``: it is not interpolated. Write ``${ x }``.
- Writing a name relative to where the string is: ``${ x }`` looks up ``x`` at
  the root. Write the full keypath (``${ section.x }``), or use ``__let__`` with
  ``"__this__"``.
- Inserting a dict, list or ``None`` with ``${...}``: use ``__splice__`` to
  copy it, a key or index to insert part of it, or ``${ x or '' }``.
- Adding a key next to a function call (``{"__if__": ..., "note": ...}``), or
  writing a dict key of the form ``__name__`` that isn't meant as a call.
- Guessing function names or argument keys. Only the functions on this page
  exist by default, with exactly the keys listed: ``list.filter`` takes
  ``iterable`` (not ``over``), ``list.loop`` takes ``over``, and
  ``datetime.first`` takes ``weekday`` (singular, full day names).
- Using ``__python__`` without the program turning it on.
- Expecting ``/`` to give an integer: ``"${ 10 / 2 }"`` is ``"5.0"``, which an
  ``integer`` field rejects. Use ``//``.
- Writing ``"true"``/``"yes"`` for a ``boolean`` field. Use a real boolean or
  ``"True"``/``"False"``.
- Giving a ``datetime`` field a date only (``"2025-09-01"``, or a date computed
  by ``__datetime.parse__``): add a time (``"... at 23:59"``) or use
  ``__datetime.at__``.
- Expecting ``"${ n }"`` in an ``any`` field to be a number: interpolation gives
  a string, and ``any`` converts nothing.
- Writing a key the schema doesn't declare: an error, unless the dict schema
  has ``extra_keys_schema``.
- Writing a template field's value without ``{"__template__": ...}``
  (``TemplateRequiredError``), or using ``__template__`` on a field that isn't a
  template or ``any`` (``UnexpectedTemplateError``), or wrapping a template
  field's schema default in ``__template__``.
- Referring to the rest of the configuration from inside a template: a
  template sees only its own value, its parameters and the global variables.
- Writing a key with a dash as a name: ``${ my-key }`` is ``my`` minus ``key``.
  Use ``${ parent["my-key"] }``.
- In TOML, leaving a dotted function key unquoted: ``__list.loop__ = ...`` makes
  nested tables. Quote it: ``"__list.loop__" = ...``. In YAML, quote strings
  that begin with ``{%`` or that contain ``${...}`` inside flow collections.


Calling smartconfig from Python
-------------------------------

.. code:: python

    smartconfig.resolve(
        cfg, spec,                    # spec: a schema dict or a Prototype class
        converters=DEFAULT_CONVERTERS,
        functions=DEFAULT_FUNCTIONS,  # None: no functions
        global_variables=None,        # names visible in ${...}, used as given
        inject_root_as=None,          # a name for the root, e.g. "root"
        filters=None,                 # extra Jinja filters
        preserve_type=False,          # keep the input's container types
        check_for_function_call=...,  # how calls are detected; None disables them
    )

Errors are in ``smartconfig.exceptions``: ``InvalidSchemaError`` (bad schema),
``ResolutionError`` (bad configuration; subclasses ``UndefinedNameError``,
``TemplateRequiredError``, ``UnexpectedTemplateError``), with ``.keypath`` and
``.reason``. ``smartconfig.validate_schema(schema)`` checks a schema on its
own. See api.rst, custom_functions.rst, custom_filters.rst and
external_variables.rst.


Telling an agent about smartconfig
----------------------------------

A project whose configuration files are resolved by smartconfig can paste this
into its ``CLAUDE.md`` or ``AGENTS.md``:

.. code:: markdown

    ## Configuration files

    The configuration files in this project are resolved by the smartconfig
    Python library, which adds its own syntax to them: `${...}` interpolation
    (not Jinja's `{{ }}`), function calls written as one-key dicts like
    `{"__list.loop__": {...}}`, and schemas. Don't guess this syntax. Before
    editing a configuration file, read smartconfig's agent cheat sheet, which is
    installed with the package. Print its path with:

        python -c "import smartconfig, pathlib; print(pathlib.Path(smartconfig.__file__).parent / 'docs' / 'agent_cheatsheet.rst')"

    (Run it in the project's environment, e.g. with `uv run python`.) The other
    pages of the documentation are in the same directory, and online at
    https://eldridgejm.github.io/smartconfig/.
