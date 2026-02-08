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
representation of a list of doubled numbers. When we resolve the configuration, the
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


Recipe 3: Using YAML tags as syntactic sugar for function calls
---------------------------------------------------------------

By default, :func:`~smartconfig.resolve` uses the ``{"__function_name__":
argument}`` syntax for function calls. While explicit, this can be verbose. If
you are using YAML, you can use YAML tags to provide a cleaner syntax.

For example, instead of writing:

.. code:: yaml

    doubled:
        __double__:
            number: 5

You could write:

.. code:: yaml

    doubled: !double 5

The idea is simple: whenever we see a YAML tag like ``!double``, we translate it
into a function call of the form ``{"__double__": <value>}``.
To achieve this, we can use `ruamel.yaml`'s `add_multi_constructor` to handle any
tag starting with `!`.

.. testcode:: python

    from ruamel.yaml import YAML, ScalarNode, SequenceNode, MappingNode
    import smartconfig

    # 1. Define a generic constructor for all tags starting with !
    def generic_constructor(loader, tag_suffix, node):
        # tag_suffix is the name of the tag, e.g. "repeat" for "!repeat"
        function_name = tag_suffix

        # construct the value based on the node type
        if isinstance(node, ScalarNode):
            value = loader.construct_scalar(node)
        elif isinstance(node, SequenceNode):
            value = loader.construct_sequence(node)
        elif isinstance(node, MappingNode):
            value = loader.construct_mapping(node)
        else:
            raise ValueError(f"Unknown node type: {type(node)}")

        return {f"__{function_name}__": value}

    # 2. Register the generic constructor
    yaml = YAML(typ='safe')
    yaml.constructor.add_multi_constructor('!', generic_constructor)

    # 3. Define a custom function to use
    def double(args):
        return int(args.input) * 2

    # 4. Define the schema
    schema = {
        "type": "dict",
        "required_keys": {
            "doubled": {"type": "integer"},
        }
    }

    # 5. Load the configuration
    yaml_str = """
    doubled: !double 5
    """

    config = yaml.load(yaml_str)

    # 6. Resolve
    result = smartconfig.resolve(
        config,
        schema,
        functions={"double": double}
    )
    print(result)

As expected, we see:

.. testoutput:: python

    {'doubled': 10}
