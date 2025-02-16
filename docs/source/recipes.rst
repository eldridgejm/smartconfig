Recipes
=======

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

    {'numbers': [1, 2, 3], 'doubled_numbers': [2, 4, 6]}
