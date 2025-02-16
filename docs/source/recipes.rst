Recipes
=======

.. testsetup:: python

   from pprint import pprint as print

Recipe 1: Include another file
------------------------------

JSON, YAML, and TOML do not have a standard way to include another file. We can extend
these formats to allow including another file by using `smartconfig`'s ability to call
custom functions.

For example, let's say the file we want to include is called ``person.json`` and looks
like this:

.. testsetup:: python

   import smartconfig
   import tempfile
   import json
   import pathlib

   # make a temporary directory
   dirpath = pathlib.Path(tempfile.mkdtemp())

   # write person.json
   with open(dirpath / 'person.json', 'w') as f:
       json.dump({"name": "Barack Obama"}, f)

   # write main.json
       with open(dirpath / 'main.json', 'w') as f:
           json.dump({
               "message": "Hello ${student.name}",
               "student": {
               "__include__": "person.json"
           }
       }, f)

.. code:: json

   {
        "name": "Barack Obama"
   }

In another JSON file named ``main.json``, we write:

.. code:: json

   {
        "message": "Hello ${student.name}",
        "student": {
            "__include__": "person.json"
        }
    }

The double underscore syntax is used to indicate that this is a function call with
``"person.json"`` as the argument.


.. testcode:: python

    import smartconfig
    import json

    def include(args):
        """Read a JSON file and include it in the configuration."""
        # args.input is assumed to be the name of the file to include
        with open(dirpath / args.input) as f:
            return json.load(f)

    schema = {
        "type": "dict",
        "required_keys": {
            "message": {"type": "string"},
            "student": {
                "type": "dict",
                "required_keys": {
                    "name": {"type": "string"}
                }
            }
        }
    }

    with open(dirpath / 'main.json') as f:
        config = json.load(f)

    result = smartconfig.resolve(
        config,
        schema,
        functions={"include": include}
    )

    print(result)

Then the result will be:

.. testoutput:: python

    {'message': 'Hello Barack Obama', 'student': {'name': 'Barack Obama'}}

.. testcleanup:: python

    import shutil
    shutil.rmtree(dirpath)


Recipe 2: Generating configurations with templated JSON, YAML, etc.
-------------------------------------------------------------------

By providing a custom function that parses a configuration string (JSON, YAML, etc.)
into a Python object, we can use Jinja2 templates to generate configurations.

In the following example, we provide a custom function called ``read_json`` that parses
a JSON string into a Python object. We then use Jinja2 templates to generate the JSON
repreesentation of a list of doubled numbers. When we resolve the configuration, the
``read_json`` function parses that templated JSON into a Python list.

.. testcode:: python

    import smartconfig
    import json

    def read_json(args):
        # args.input is assumed to be a JSON string
        return json.loads(args.input)

    schema = {
        "type": "dict",
        "required_keys": {
            "numbers": {
                "type": "list",
                "element_schema": {"type": "integer"}
        },
            "doubled_numbers": {
                "type": "list",
                "element_schema": {"type": "integer"}
            }
        }
    }

    config = {
        "numbers": [1, 2, 3],
        "doubled_numbers": {
            "__read_json__": """
            [
                {% for number in numbers %}
                    ${ number * 2 }${ "," if not loop.last }
                {% endfor %}
            ]
            """
        }
    }

    print(smartconfig.resolve(
        config,
        schema,
        functions={"read_json": read_json}
    ))

The result will be:

.. testoutput:: python

    {'doubled_numbers': [2, 4, 6], 'numbers': [1, 2, 3]}


Recipe 3: Suggested conventions for including external variables
----------------------------------------------------------------

Sometimes you may want to allow a configuration to access "external variables" that have
been defined elsewhere. For example, your project may include a configuration file at
its root and many configuration files in subdirectories. You may want the subdirectory
configurations to be able to refer to variables defined in the root configuration file
so that they do not need to be duplicated.

One way to do this is with the ``global_variables`` argument to :func:`smartconfig.resolve`,
however, this is to be avoided. This is because the top-level keys of the configuration
and the keys of the global variables are merged together into the same namespace, which
can lead to key collisions and unexpected behavior. Rather, the ``global_variables``
argument should be used for things like global functions that should be available during
resolution, and whose names are known not to collide with any built-in Jinja2 functions.

Instead, it is better to combine the configuration with the external variables into one
dictionary that becomes the new root configuration. The suggested convention is to use a
"this" key to refer to the configuration currently being processed, and an "vars" key to
refer to the external variables. Under this convention, internal references that were once
``${key}`` become ``${this.key}``, and external references that were once ``${key}``
become ``${vars.key}``, making it more explicit where the value is coming from.

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

    print(smartconfig.resolve(root, schema))

The result will be:

.. testoutput:: python

    {'this': {'course_name': 'Introduction to Python',
              'date_of_first_discussion': datetime.date(2025, 1, 17),
              'date_of_first_lecture': datetime.date(2025, 1, 10),
              'message': ['Welcome to Introduction to Python!',
                          'The first lecture is on 2025-01-10.',
                          'The first discussion is on 2025-01-17.']},
     'vars': {'date_of_first_lecture': '2025-01-10'}}

Note that under this convention, the external variables are also resolved.
