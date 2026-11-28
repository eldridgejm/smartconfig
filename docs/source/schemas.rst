.. _schemas:

Schemas
=======

In order for `smartconfig` to properly resolve a configuration, it first needs
to know the expected structure and types of the configuration. This structure
is given by a **schema**: a dictionary defining which keys are required or
optional, the types of values, and any default values.

A dict schema can also be written as a Python class, a :ref:`prototype
<prototypes>`, which resolves to an instance of the class.

.. testsetup::

    import smartconfig
    from pprint import pprint as print

More precisely, a schema dictionary follows the formal grammar below:

.. code:: text

    <SCHEMA> = (
        <DICT_SCHEMA> | <LIST_SCHEMA> | <VALUE_SCHEMA> | <ANY_SCHEMA> | <TEMPLATE_SCHEMA>
    )

    <DICT_SCHEMA> = {
        "type": "dict",
        ["required_keys": {<KEY_NAME>: <SCHEMA>, ...}],
        ["optional_keys": {<KEY_NAME>: (<SCHEMA> | <SCHEMA_WITH_DEFAULT>), ...}],
        ["extra_keys_schema": <SCHEMA>],
        ["nullable": (True | False)],
    }

    <LIST_SCHEMA> = {
        "type": "list",
        "element_schema": <SCHEMA>,
        ["nullable": (True | False)]
    }

    <VALUE_SCHEMA> = {
        "type": <VALUE_TYPE>,
        ["nullable": (True | False)]
    }

    <VALUE_TYPE> = (
        "string" | "integer" | "float" | "boolean" | "date" | "datetime"
        | <NAME OF A CUSTOM CONVERTER>
    )

    <ANY_SCHEMA> = {
        "type": "any",
        ["nullable": (True | False)]
    }

    <TEMPLATE_SCHEMA> = {
        "type": "template",
        "schema": <SCHEMA>,
        "parameters": [<NAME>, ...],
        ["nullable": (True | False)]
    }

    <SCHEMA_WITH_DEFAULT> = (
        <DICT_SCHEMA_WITH_DEFAULT>
        | <LIST_SCHEMA_WITH_DEFAULT>
        | <VALUE_SCHEMA_WITH_DEFAULT>
        | <ANY_SCHEMA_WITH_DEFAULT>
        | <TEMPLATE_SCHEMA_WITH_DEFAULT>
    )

The ``DICT_SCHEMA_WITH_DEFAULT``, ``LIST_SCHEMA_WITH_DEFAULT``,
``VALUE_SCHEMA_WITH_DEFAULT``, ``ANY_SCHEMA_WITH_DEFAULT`` and
``TEMPLATE_SCHEMA_WITH_DEFAULT`` grammars are the
same as their non-default counterparts, but with an additional field named
`default` that specifies the default value should that part of the
configuration be missing.

A default is resolved just like a value written in the configuration: it is
interpolated, its function calls are evaluated, and it is converted, and a dict
default gets the defaults of its own keys:

.. testcode::

    schema = {
        "type": "dict",
        "required_keys": {"x": {"type": "integer"}},
        "optional_keys": {
            "y": {"type": "integer", "default": "${ x + 1 }"},
            "z": {
                "type": "dict",
                "optional_keys": {"w": {"type": "string", "default": "hi"}},
                "default": {},
            },
        },
    }
    print(smartconfig.resolve({"x": 1}, schema))

.. testoutput::

    {'x': 1, 'y': 2, 'z': {'w': 'hi'}}

The default of a template schema is the template as written, *without* a
``__template__`` wrapper. Wrapping it is an
:class:`~smartconfig.exceptions.UnexpectedTemplateError`.

.. testcode::

    schema = {
        "type": "dict",
        "optional_keys": {
            "greeting": {
                "type": "template",
                "schema": {"type": "string"},
                "parameters": ["name"],
                "default": "Hello, ${ name }!",
            },
        },
    }
    result = smartconfig.resolve({}, schema)
    print(result["greeting"].evaluate({"name": "Ada"}))

.. testoutput::

    'Hello, Ada!'

Anywhere a schema is expected, you can also provide a **dynamic schema**.
A dynamic schema is a Python function that takes a configuration value and its
keypath as input and returns a schema dictionary. This allows the schema to be
determined at runtime based on the configuration itself. This is particularly
useful for handling polymorphic lists or dictionaries where the schema of an
element depends on its content (e.g., a "type" field).
(See :ref:`dynamic_schemas_example` for an example).

The function gets the *raw* value, as written in the configuration, before any
interpolation or function evaluation: a ``"${...}"`` string or a function call
is passed as it is. When an optional key is missing, the function is called
with ``None``, so that it can return a schema with a default. What it returns is
validated like any other schema, so it may have a ``default`` only where one
could be written: under ``required_keys``, a returned default is an
:class:`~smartconfig.exceptions.InvalidSchemaError`.

A **template schema** marks a field whose value is evaluated later, possibly
many times: its value is kept as written and resolves to a
:class:`smartconfig.types.Template`. ``"schema"`` describes the value once it is
evaluated, and ``"parameters"`` lists the template's parameters: the names
whose values are given each time it is evaluated (the list may be empty). Like
a function's parameters, each call to
:meth:`Template.evaluate <smartconfig.types.Template.evaluate>` must give exactly
these, no more and no fewer. A parameter may not have the same name as one of
the template's top-level keys: both can be referenced by name, so ``${ name }``
would be ambiguous. Nested keys are not affected. The inner schema may not have
a top-level default; put the default on the template schema. The inner schema
may contain template schemas: a template inside a template sees the parameters
of the templates around it. (See :ref:`template_fields_example`.)

Schemas can be validated using the :func:`smartconfig.validate_schema`
function.

Examples
~~~~~~~~

Example 1: A simple schema
^^^^^^^^^^^^^^^^^^^^^^^^^^

This minimal schema shows required string, integer, and list fields.

Input:

.. testcode::

    config = {
        "name": "Barack Obama",
        "age": 63,
        "enrolled_in": ["Math 100", "History 101", "Physics 200"],
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"},
            },
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    {'age': 63,
     'enrolled_in': ['Math 100', 'History 101', 'Physics 200'],
     'name': 'Barack Obama'}

Example 2: Allowing extra keys
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, `smartconfig` will raise an error if the configuration contains
keys not specified in the schema. Sometimes, however, it is useful to allow the
user to provide "extra" keys that are not specified in the schema. This is most
often the case when we want to allow the user to define a mapping whose keys
are not known in advance.

Input:

.. testcode::

    config = {
        "name": "Barack Obama",
        "age": 63,
        "enrolled_in": ["Math 100", "History 101"],
        "grades": {"Math 100": "A-", "History 101": "A"},
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"},
            },
            "grades": {"type": "dict", "extra_keys_schema": {"type": "string"}},
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    {'age': 63,
     'enrolled_in': ['Math 100', 'History 101'],
     'grades': {'History 101': 'A', 'Math 100': 'A-'},
     'name': 'Barack Obama'}

Example 3: Allowing nullable values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Mark a field as nullable when ``None`` is an allowed value in the configuration.
``nullable`` defaults to ``False``, except for the ``any`` type, which accepts
``None`` unless it is given ``"nullable": False``.

Input:

.. testcode::

    config = {"name": "Barack Obama", "age": None}
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer", "nullable": True},
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    {'age': None, 'name': 'Barack Obama'}

Example 4: Optional keys and defaults
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Optional keys can be omitted entirely, and defaults populate missing values.

Input:

.. testcode::

    config = {"name": "Barack Obama", "age": 63, "enrolled_in": []}
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "enrolled_in": {
                "type": "list",
                "element_schema": {"type": "string"},
            },
        },
        "optional_keys": {
            "email": {"type": "string"},
            "standing": {"type": "string", "default": "undergraduate"},
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    {'age': 63,
     'enrolled_in': [],
     'name': 'Barack Obama',
     'standing': 'undergraduate'}

Example 5: Nested containers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Schemas can nest lists of dictionaries to any depth.

Input:

.. testcode::

    config = [
        {"name": "Barack Obama", "age": 63, "enrolled_in": ["History 101"]},
        {"name": "Kamala Harris", "age": 60, "enrolled_in": ["Law 200"]},
    ]
    schema = {
        "type": "list",
        "element_schema": {
            "type": "dict",
            "required_keys": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "enrolled_in": {
                    "type": "list",
                    "element_schema": {"type": "string"},
                },
            },
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    [{'age': 63, 'enrolled_in': ['History 101'], 'name': 'Barack Obama'},
     {'age': 60, 'enrolled_in': ['Law 200'], 'name': 'Kamala Harris'}]

Example 6: "Any" schema
^^^^^^^^^^^^^^^^^^^^^^^

Use the ``any`` type when a value should be accepted without type checking.

Input:

.. testcode::

    config = {"name": "Barack Obama", "metadata": {"favorite": "pineapple pizza"}}
    schema = {
        "type": "dict",
        "required_keys": {
            "name": {"type": "string"},
            "metadata": {"type": "any"},
        },
    }
    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    {'metadata': {'favorite': 'pineapple pizza'}, 'name': 'Barack Obama'}

.. _dynamic_schemas_example:

Example 7: Dynamic schemas
^^^^^^^^^^^^^^^^^^^^^^^^^^

Dynamic schemas are most useful for validating/resolving the elements of
containers that can contain multiple types of elements. For example, suppose a
list can contain both ``Professor`` and ``Student`` entries, each with
different fields. A dynamic schema can be used to select the appropriate schema
based on a "type" field in each entry.

Input:

.. testcode::

    def person_schema(element, keypath):
        if element.get("type") == "student":
            return {
                "type": "dict",
                "required_keys": {
                    "type": {"type": "string"},
                    "name": {"type": "string"},
                    "major": {"type": "string"},
                },
            }
        elif element.get("type") == "professor":
            return {
                "type": "dict",
                "required_keys": {
                    "type": {"type": "string"},
                    "name": {"type": "string"},
                    "department": {"type": "string"},
                },
                "optional_keys": {
                    "rank": {"type": "string", "default": "assistant professor"},
                },
            }
        else:
            raise smartconfig.exceptions.ResolutionError(
                f"Unknown person type: {element.get('type')}", keypath
            )

    config = [
        {"type": "student", "name": "Alice", "major": "Physics"},
        {"type": "professor", "name": "Bob", "department": "Math"},
    ]

    schema = {
        "type": "list",
        "element_schema": person_schema,
    }

    print(smartconfig.resolve(config, schema))

Output:

.. testoutput::

    [{'major': 'Physics', 'name': 'Alice', 'type': 'student'},
     {'department': 'Math',
      'name': 'Bob',
      'rank': 'assistant professor',
      'type': 'professor'}]


.. _template_fields_example:

Example 8: Template fields
^^^^^^^^^^^^^^^^^^^^^^^^^^

Some values can only be evaluated later, by whoever uses the configuration:
for example, a page that is made once for each homework. A field whose schema
has ``"type": "template"`` holds such a value. Its value is written in a
``__template__`` wrapper, kept as written, and resolves to a
:class:`smartconfig.types.Template`:

.. testcode::

    schema = {
        "type": "dict",
        "required_keys": {
            "course": {"type": "string"},
            "page": {
                "type": "template",
                "schema": {
                    "type": "dict",
                    "required_keys": {
                        "title": {"type": "string"},
                        "points": {"type": "integer"},
                    },
                },
                "parameters": ["publication", "course"],
            },
        },
    }

    config = {
        "course": "DSC 40B",
        "page": {
            "__template__": {
                "title": "${ course }: ${ publication.name }",
                "points": "${ publication.points * 2 }",
            }
        },
    }

    result = smartconfig.resolve(config, schema)
    page = result["page"]
    print(page)
    print(page.source)

Output:

.. testoutput::

    Template(at "page", parameters: publication, course)
    {'points': '${ publication.points * 2 }',
     'title': '${ course }: ${ publication.name }'}

:meth:`Template.evaluate <smartconfig.types.Template.evaluate>` evaluates the template:
interpolation, function calls, type conversion and defaults, as
:func:`smartconfig.resolve` does. It takes a mapping from each of the template's
parameters to its value. A template is evaluated on its own, so the rest of the
configuration is not visible to it: ``course`` is not part of the template, so
it is a parameter and is passed in:

.. testcode::

    print(
        page.evaluate(
            {"publication": {"name": "Homework 1", "points": 5}, "course": "DSC 40B"}
        )
    )

Output:

.. testoutput::

    {'points': 10, 'title': 'DSC 40B: Homework 1'}

A template keeps everything that was passed to :func:`smartconfig.resolve`:
the functions, filters, converters and global variables it uses are the same
ones the rest of the configuration uses. If a parameter has the same name as a
global variable, the parameter wins.

**What is checked when the configuration is resolved.** The value must be
written with ``__template__``, copied with :ref:`__use__ <func-use>`, or
produced by another function call that makes a template (an ``__if__`` that
chooses between two ``__template__`` values, say): otherwise
:class:`exceptions.TemplateRequiredError <smartconfig.exceptions.TemplateRequiredError>`
is raised. Whichever way the template is made, it gets this field's inner schema
and parameters. Its structure is checked against the inner schema: required and
unexpected keys, dicts versus lists, nulls. Nothing in it is evaluated. A
function call inside it must name a known function, or resolution fails with an
error; the call's input, and what it returns, are not checked until the template
is evaluated. Recall the schema from above:

.. code:: python

    schema = {
        "type": "dict",
        "required_keys": {
            "course": {"type": "string"},
            "page": {
                "type": "template",
                "schema": {
                    "type": "dict",
                    "required_keys": {
                        "title": {"type": "string"},
                        "points": {"type": "integer"},
                    },
                },
                "parameters": ["publication", "course"],
            },
        },
    }

A page without ``points`` is an error, even though the template is not
evaluated:

.. testcode::

    bad = {"course": "DSC 40B", "page": {"__template__": {"title": "Homework"}}}

    try:
        smartconfig.resolve(bad, schema)
    except smartconfig.exceptions.ResolutionError as exc:
        print(exc.keypath)
        print(exc.reason)

Output:

.. testoutput::

    ('page', 'points')
    'Dictionary is missing required key "points".'

So is a call to a function that doesn't exist, even though the call is never
made:

.. testcode::

    bad = {
        "course": "DSC 40B",
        "page": {"__template__": {"title": "Homework", "points": {"__nope__": 1}}},
    }

    try:
        smartconfig.resolve(bad, schema)
    except smartconfig.exceptions.ResolutionError as exc:
        print(exc.keypath)
        print(exc.reason)

Output:

.. testoutput::

    ('page', 'points')
    'Invalid function call: Unknown function: nope'

**What is checked when the template is evaluated.** First, the names given
must be exactly the template's parameters, no more and no fewer:

.. testcode::

    try:
        page.evaluate({"publication": {"name": "Homework 1", "points": 5}})
    except smartconfig.exceptions.ResolutionError as exc:
        print(exc.reason)

Output:

.. testoutput::

    "Missing parameters: course. This template's parameters: publication, course."

Then, the names its strings use. A name that is not defined raises
:class:`exceptions.UndefinedNameError <smartconfig.exceptions.UndefinedNameError>`,
which suggests a close name or lists the names that were available:

.. testcode::

    typo = smartconfig.types.Template(
        "${ publcation.name }",
        schema={"type": "string"},
        parameters=["publication"],
        keypath=["page", "title"],
    )

    try:
        typo.evaluate({"publication": {"name": "Homework 1"}})
    except smartconfig.exceptions.UndefinedNameError as exc:
        print(exc.keypath)
        print(exc.reason)

Output:

.. testoutput::

    ('page', 'title')
    '\'publcation\' is undefined. Did you mean "publication"?'

.. _nested_templates:

**Templates inside templates.** A template's value can contain template fields.
For example, a course schedule might have one entry per lecture, and inside each
lecture one link per video. The lecture is a template with parameter
``publication``, and its ``videos`` field is a template with parameter
``link``, inside it:

.. testcode::

    schema = {
        "type": "dict",
        "required_keys": {
            "lecture": {
                "type": "template",
                "parameters": ["publication"],
                "schema": {
                    "type": "dict",
                    "required_keys": {
                        "title": {"type": "string"},
                        "videos": {
                            "type": "template",
                            "parameters": ["link"],
                            "schema": {
                                "type": "dict",
                                "required_keys": {
                                    "text": {"type": "string"},
                                    "url": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            }
        },
    }

    config = {
        "lecture": {
            "__template__": {
                "title": "Lecture ${ publication.number }: ${ publication.topic }",
                "videos": {
                    "__template__": {
                        "text": "${ link.title } (lecture ${ publication.number })",
                        "url": "${ link.url }",
                    }
                },
            }
        }
    }

    result = smartconfig.resolve(config, schema)

Evaluating the outer template keeps the inner one's value as written and puts a
``Template`` in its place. The inner template sees the parameters of the
template around it, with the values of the evaluation that made it, so
``publication`` is not passed again:

.. testcode::

    publication = {
        "number": 4,
        "topic": "Hashing",
        "videos": [
            {"title": "Part 1", "url": "https://example.com/4-1"},
            {"title": "Part 2", "url": "https://example.com/4-2"},
        ],
    }

    lecture = result["lecture"].evaluate({"publication": publication})
    print(lecture["title"])
    print(lecture["videos"])
    print(lecture["videos"].outer_parameters["publication"]["number"])

    for link in publication["videos"]:
        print(lecture["videos"].evaluate({"link": link}))

Output:

.. testoutput::

    'Lecture 4: Hashing'
    Template(at "lecture.videos", parameters: link; outer: publication)
    4
    {'text': 'Part 1 (lecture 4)', 'url': 'https://example.com/4-1'}
    {'text': 'Part 2 (lecture 4)', 'url': 'https://example.com/4-2'}

Templates nest to any depth, and the same rules hold at each level:

- The inner field's value is written with its own ``__template__``, as at the
  top level. A missing wrapper is a
  :class:`exceptions.TemplateRequiredError <smartconfig.exceptions.TemplateRequiredError>`,
  found when the configuration is resolved. When the configuration is resolved,
  the inner value's structure is checked against its schema, like the outer
  one's.
- The inner template's
  :attr:`~smartconfig.types.Template.parameters` are only the ones its schema
  declares, and :meth:`~smartconfig.types.Template.evaluate` takes exactly those.
  The values it sees from the templates around it are its
  :attr:`~smartconfig.types.Template.outer_parameters`. A parameter wins over
  a global variable of the same name here too.
- The inner template sees the parameters of the templates around it, and
  nothing else of theirs. It is evaluated on its own, so the outer template's
  keys (``title`` above) are not names in it.
- A parameter of the inner template, or a top-level key of its value, named
  like a parameter of a template around it would be ambiguous, so it is an
  error: an
  :class:`exceptions.InvalidSchemaError <smartconfig.exceptions.InvalidSchemaError>`
  where the schema shows it, and otherwise a
  :class:`exceptions.ResolutionError <smartconfig.exceptions.ResolutionError>`
  when the configuration is resolved.
- A template whose inner schema is itself a template schema evaluates to a
  ``Template``: ``{"__template__": {"__template__": ...}}``.
- A ``__use__`` inside an inner template's value is expanded when the
  configuration is resolved, like any ``__use__`` inside a template. A
  ``__use__`` written as the whole value of an inner template field is replaced
  by the value it copies, which leaves the field without a wrapper; write it as
  ``{"__template__": {"__use__": ...}}`` instead. A template inside another
  doesn't exist until the outer one is evaluated, so it can't be the target of a
  ``__use__``.
- An inner ``Template`` passed into :func:`smartconfig.resolve` keeps its outer
  parameters.

**Other details.**

- A ``__template__`` wrapper on a field of type ``"any"`` also resolves to a
  ``Template``, with schema ``{"type": "any"}`` and no parameters (inside a
  template, it sees the outer parameters too). On a
  field of any other type it is an error
  (:class:`exceptions.UnexpectedTemplateError <smartconfig.exceptions.UnexpectedTemplateError>`).
- A dynamic schema inside a template is called twice: once when the
  configuration is resolved, to check the template's structure, and again each
  time the template is evaluated. Both times it is called with the value as
  written, before any interpolation, so it should choose a schema by looking at
  the value's structure (which keys are present, say) rather than at values that
  contain ``${...}``:

  .. testcode::

      def score_schema(cfg, keypath):
          print(cfg)
          if "points" in cfg:
              return {"type": "dict", "required_keys": {"points": {"type": "integer"}}}
          return {"type": "dict", "required_keys": {"grade": {"type": "string"}}}

      schema = {
          "type": "dict",
          "required_keys": {
              "score": {
                  "type": "template",
                  "schema": score_schema,
                  "parameters": ["n"],
              }
          },
      }

      result = smartconfig.resolve(
          {"score": {"__template__": {"points": "${ n * 2 }"}}}, schema
      )
      print(result["score"].evaluate({"n": 5}))

  Output:

  .. testoutput::

      {'points': '${ n * 2 }'}
      {'points': '${ n * 2 }'}
      {'points': 10}
