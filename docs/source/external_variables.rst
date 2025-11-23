External Variables
==================

.. testsetup:: python

    import smartconfig
    from pprint import pprint as print
    from datetime import date

Sometimes you may want to allow a configuration to access "external variables" that have
been defined elsewhere. For example, your project may include a configuration file at
its root and many configuration files in subdirectories. You may want the subdirectory
configurations to be able to refer to variables defined in the root configuration file
so that they do not need to be duplicated.
Or, you might want to pass environment variables, secrets, or other runtime data into
the configuration resolution process.

`smartconfig` provides a `global_variables` mechanism for this. However, there
is also a recommended design pattern that often leads to cleaner, more
maintainable configurations.

The ``global_variables`` Argument
---------------------------------

The `global_variables` argument to :func:`smartconfig.resolve` allows you to pass a
dictionary of variables that will be available to Jinja2 during string interpolation.

.. testcode:: python

    config = {
        "greeting": "Hello, ${user}!"
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "greeting": {"type": "string"}
        }
    }

    # "user" is passed as a global variable
    result = smartconfig.resolve(
        config,
        schema,
        global_variables={"user": "Alice"}
    )
    print(result)

.. testoutput:: python

    {'greeting': 'Hello, Alice!'}

Global variables are searched last, after local variables (defined on nodes) and the
configuration root. This means that if a key exists in the configuration, it will shadow
a global variable of the same name.

As discussed below, global variables should generally not be used to pass external variables
whose names are unknown in advance, as this can lead to naming collisions and
namespace pollution. Rather, the intended usecase for global variables is to provide
extra functions or constants to the string interpolation engine. These functions or constants
should be made known in advance so that collisions can be avoided.

.. _recipes_external_variables:

Suggested Convention for External Variables
-------------------------------------------

Using `global_variables` to pass external variables whose names are unknown in
advance can lead to namespace pollution and collisions because the global
variables are merged into the same namespace as the configuration keys.

A more robust approach is to combine the configuration with the external variables into
one dictionary that becomes the new root configuration. A common convention is to use a
"this" key to refer to the configuration currently being processed, and a "vars" key to
refer to the external variables.

Under this convention:

*   Internal references that were once ``${key}`` become ``${this.key}``.
*   External references that were once ``${key}`` become ``${vars.key}``.

This makes it explicit where each value is coming from.

As an example of this, consider the following configuration:

.. testcode:: python

    config = {
        "course_name": "Introduction to Python",
        "date_of_first_lecture": "${ vars.date_of_first_lecture }",
        "date_of_first_discussion": "7 days after ${this.date_of_first_lecture}",
        "message": [
            "Welcome to ${this.course_name}!",
            "The first lecture is on ${this.date_of_first_lecture}.",
            "The first discussion is on ${this.date_of_first_discussion}."
        ]
    }

    external_variables = {
        "date_of_first_lecture": "2025-01-10"
    }

    # Wrap config and variables together
    root = {
        "this": config,
        "vars": external_variables
    }

    schema = {
        "type": "dict",
        "required_keys": {
            "this": {
                "type": "dict",
                "required_keys": {
                    "course_name": {"type": "string"},
                    "date_of_first_lecture": {"type": "date"},
                    "date_of_first_discussion": {"type": "date"},
                    "message": {"type": "list", "element_schema": {"type": "string"}}
                }
            },
            "vars": {
                "type": "dict",
                "extra_keys_schema": {
                    "type": "any",
                }
            }
        }
    }

    result = smartconfig.resolve(root, schema)
    print(result)

The result will be:

.. testoutput:: python

    {'this': {'course_name': 'Introduction to Python',
              'date_of_first_discussion': datetime.date(2025, 1, 17),
              'date_of_first_lecture': datetime.date(2025, 1, 10),
              'message': ['Welcome to Introduction to Python!',
                          'The first lecture is on 2025-01-10.',
                          'The first discussion is on 2025-01-17.']},
     'vars': {'date_of_first_lecture': '2025-01-10'}}

Note that under this convention, the external variables are also resolved, which means
you can use `smartconfig` features within your external variables as well.
