Recipes
=======

Recipe 1: Include another file
------------------------------

JSON, YAML, and TOML do not have a standard way to include another file. We can extend
these formats to allow including another file by using `smartconfig`'s ability to call
custom functions.

For example, let's say the file we want to include is called ``person.json`` and looks
like this:

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


.. code:: python

    import smartconfig
    import json

    def include(args):
        """Read a JSON file and include it in the configuration."""
        # args.input is assumed to be the name of the file to include
        with open(args.input) as f:
            return json.load(f)

    schema = {
        "type": "dict",
        "required_keys": {
            "message": {"type": "string"},
            "student": {"type": "string"}
        }
    }

    with open('main.json') as f:
        config = json.load(f)

    result = smartconfig.resolve(
        config,
        schema,
        functions={"include": include}
    )

Then the result will be:

.. code:: python

    {
        "message": "Hello Barack Obama",
        "student": {
            "name": "Barack Obama"
        }
    }




