# smartconfig

`smartconfig` is a Python library for extending standard configuration formats
like JSON, YAML, TOML, and others with "smart" features, such as string
interpolation, natural language parsing, type validation, function calls, and
control flow.

See the [documentation](https://eldridgejm.github.io/smartconfig/) for more information.

## Use Cases and Example

Python programs that require user configuration often use simple configuration formats such as JSON, YAML, or TOML. These formats are easier to read and write than coding languages, but they may not support more advanced features like string interpolation, date parsing, or type checking. Another approach is to use a full-fledged programming language to define the configuration, such as Python itself. However, this approach vastly increases the possible complexity of the configuration file, and it requires that users know how to write Python code.

`smartconfig` aims to bridge the gap between these two approaches by providing a simple way to extend simple configuration formats with "smart" features. To see how this works, consider the following example. Suppose you have a configuration file in JSON format that looks like this:

```json
{
    "course_name": "Introduction to Python",
    "date_of_first_lecture": "2025-01-10",
    "date_of_first_discussion": "3 days before ${first_lecture}",
    "message": [
        "Welcome to ${course_name}!",
        "The first lecture is on ${first_lecture}.",
        "The first discussion is on ${first_discussion}.",
        {
            "__if__": {
                "condition": "${first_discussion < first_lecture}",
                "then": "Note! The first discussion is before the first lecture.",
                "else": "The first discussion is after the first lecture."
            }
        }
    ]
}
```

Notice the use of the `${...}` syntax to refer to other values in the
configuration file and that the `date_of_first_discussion` key is defined
relative to the `date_of_first_lecture` key using natural language. There is
also a conditional which checks if the date of the first discussion is before
the date of the first lecture and formats the message accordingly.

None of these features are provided by standard JSON parsers. Of course, if we
try to load this configuration file using Python's `json` module, we will not
see anything special happen; the references will not be resolved.

Now let's use `smartconfig` to "resolve" the configuration:

```python
import smartconfig
import json

# read the configuration json
with open('example.json') as f:
    config = json.load(f)

# first, we write a "schema" defining the structure of the configuration
schema = {
    "type": "dict",
    "required_keys": {
        "course_name": {"type": "string"},
        "date_of_first_lecture": {"type": "date"},
        "date_of_first_discussion": {"type": "date"},
        "message": {"type": "list", "element_schema": {"type": "string"}}
    }
}

# now we "resolve" the configuration
result = smartconfig.resolve(config, schema)
print(result)
```

We will see the following output:

```python
{'course_name': 'Introduction to Python',
 'date_of_first_discussion': datetime.date(2025, 1, 7),
 'date_of_first_lecture': datetime.date(2025, 1, 10),
 'message': ['Welcome to Introduction to Python!',
             'The first lecture is on 2025-01-10.',
             'The first discussion is on 2025-01-07.',
             'Note! The first discussion is before the first lecture.']}
```

Notice that the `${...}` references have been resolved, and the date of the
first discussion, defined relative to the date of the first lecture in the
original JSON, has been calculated correctly. The conditional has also
been evaluated.

This example demonstrates the most basic use case of `smartconfig`: extending simple configuration formats. But `smartconfig` provides many more features that can be used to create powerful and flexible configuration files.

## Features

`smartconfig` supports extending configuration formats with the following features:

- **String interpolation**: Use `${...}` to refer to other values in the configuration file. This helps avoid tedious duplication and the errors that can arise from it.
- **Natural language parsers**: `smartconfig` includes natural language parsers for dates, numbers, and boolean values. When combined with string interpolation, this allows you to define values relative to other values in the configuration file. For example, you can define a value as `7 days after ${start_date}`, or `${previous_lecture_number} + 1`.
- **Function calls**: `smartconfig` defines a syntax for calling functions in the configuration file. This allows the user to specify complex values that are calculated at runtime. Functions are provided for merging dictionaries, concatenating lists, etc., and developers can define their own functions as well.
- **Complex control flow**: The Jinja2 templating engine is used under the hood, which means that you can use Jinja2's control flow constructs like `if` statements, `for` loops, and more to define complex values in your configuration file. You can also use Jinja2 filters to transform values in your configuration file, as in `${value | capitalize}` to capitalize a string.
- **Default values**: Default values can be provided so that the user can save typing and highlight what's important by only specifying the values that are different from the default.
- **Basic type checking**: `smartconfig` can check that values in the configuration file are of the expected type. For example, you can specify that a value should be a date, a number, or a boolean, and `smartconfig` will raise an error if the value is not of the expected type.

Additionally, `smartconfig` provides the following features to developers:

- **Extensibility**: `smartconfig` is designed to be easily extensible. Developers can define custom parsers for custom natural language parsing, custom functions for complex runtime behavior, and custom filters for transforming values during string interpolation.
- **Format agnostic**: `smartconfig` can be used with any configuration format that can be loaded into a Python dictionary. This includes JSON, YAML, TOML, and more.
