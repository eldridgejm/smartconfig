# Changelog

## 0.7.1

### The Prototype functions move to `smartconfig.prototypes`

`schema`, `template`, `schema_of` and `instantiate` are now in the new `smartconfig.prototypes` module, and are no longer at the top level. Their names read as the general schema and template tools there, and `smartconfig.template` was easily confused with the `__template__` function and `smartconfig.types.Template`. `smartconfig.Prototype` stays at the top level (and is also `smartconfig.prototypes.Prototype`).

```python
import smartconfig
from smartconfig.prototypes import schema, template, schema_of, instantiate

class Config(smartconfig.Prototype):
    calendar: Annotated[dict[str, Any] | None, schema(CALENDAR_SCHEMA)] = None
```

Code written for 0.7.0 changes `smartconfig.schema(...)` to `smartconfig.prototypes.schema(...)`, and likewise for the other three.

## 0.7.0

### Prototypes are back, as dataclasses

A configuration can again be described by a class: a subclass of `smartconfig.Prototype`. Prototypes were removed in 0.6.0 because they couldn't say everything a schema can. They return redesigned:

- A subclass of `Prototype` is a stdlib dataclass (with keyword-only fields). `__init__`, `__eq__`, `__repr__` and `dataclasses.field(default_factory=...)` come from `dataclasses`, and type checkers know its fields (`Prototype` is marked with `typing.dataclass_transform`).
- A field's schema is inferred from its type hint: `str`, `int`, `float`, `bool`, `datetime.date`, `datetime.datetime`, `Any`, `T | None` (nullable), `list[T]`, `dict[str, T]` (`extra_keys_schema`) and nested prototypes. Any other type hint is a `TypeError` when the class is defined, naming the class and the field.
- A field is optional exactly when it has a default, which becomes its schema's default, and nullable exactly when its type includes `None`. There is no `NotRequired`.
- Anything else is said with an explicit schema, used as given: `Annotated[T, smartconfig.schema(...)]`, which also takes a dynamic schema, and `Annotated[Template, smartconfig.template(<schema>, parameters=[...])]` for template fields.
- The class option `extra_keys` gives the schema of extra keys (as a type or an explicit schema), as in `class Website(Prototype, extra_keys=str)`. They are kept in the instance's `extra_keys` attribute.

```python
from dataclasses import field
from typing import Annotated, Any
import smartconfig
from smartconfig.types import Template

class Build(smartconfig.Prototype):
    jobs: int | None = None

class Config(smartconfig.Prototype):
    title: Annotated[Template, smartconfig.template({"type": "string"}, ["publication"])]
    calendar: Annotated[dict[str, Any] | None, smartconfig.schema(CALENDAR_SCHEMA)] = None
    build: Build = field(default_factory=Build)
    ignore: list[str] = field(default_factory=list)

config = smartconfig.resolve(raw, Config)  # a Config instance
```

`resolve(cfg, SomeProtoClass)` resolves against the class's schema, so interpolation, functions, global variables and errors (with their keypaths) are exactly those of the equivalent schema dict, and returns an instance. `smartconfig.schema_of(cls)` gives that schema, and `smartconfig.instantiate(cls, resolved)` builds an instance from a resolved dict.

## 0.6.1

### Templates inside templates

A template's value can contain template fields. This was an error in 0.6.0 ("Templates don't nest"); it is now allowed:

```python
inner = {"type": "template", "schema": {"type": "string"}, "parameters": ["link"]}
schema = {
    "type": "dict",
    "required_keys": {
        "lecture": {
            "type": "template",
            "schema": {"type": "dict", "required_keys": {"video": inner}},
            "parameters": ["publication"],
        }
    },
}
config = {
    "lecture": {
        "__template__": {
            "video": {"__template__": "${ link.title } (lecture ${ publication.number })"}
        }
    }
}
lecture = resolve(config, schema)["lecture"].evaluate({"publication": {"number": 4}})
lecture["video"].evaluate({"link": {"title": "Part 1"}})  # "Part 1 (lecture 4)"
```

- The inner field's value is written with its own `__template__`. Evaluating the outer template keeps it as written and gives a `Template` in its place.
- The inner template sees the parameters of the templates around it, with the values of the evaluation that made it, as `Template.outer_parameters` (new, read-only). It sees nothing else of theirs: their keys are not names in it. Its own `parameters` are only the ones its schema declares, and `evaluate` takes exactly those.
- Templates nest to any depth. When the configuration is resolved, each inner value's structure is checked against its schema, and `__use__` inside it is expanded.
- A parameter of an inner template, or a top-level key of its value, named like a parameter of a template around it is an error: an `InvalidSchemaError` from `validate_schema` where the schema shows it, and a `ResolutionError` otherwise.
- A `__use__` written as the whole value of an inner template field leaves the field without its wrapper, and is an error. Write `{"__template__": {"__use__": ...}}`. A template inside another can't be the target of a `__use__`.
- An inner `Template` passed into `resolve()` keeps its outer parameters.
- A `__template__` wrapper on an `any` field inside a template gives a `Template` too (it was an `UnexpectedTemplateError`).
- A template schema whose inner schema is a template schema is allowed (it was an `InvalidSchemaError`); the template evaluates to a `Template`.

API:

- `Template` takes a keyword-only `outer_parameters`, and its `repr` names them (`Template(at "lecture.video", parameters: link; outer: publication)`). A parameter named like an outer parameter is a `ValueError`.
- `ResolutionContext` has a `template_parameters` field: the parameters of the templates being evaluated, looked up after the document and before the global variables. `UndefinedNameError.available` lists them.
- `UnexpectedTemplateError` is now raised only for a `__template__` wrapper on a field that is neither a template nor `any`. Its `enclosing` is the innermost template around the wrapper.

## 0.6.0

This release has many breaking changes; they are collected under "Breaking changes" below. Prototypes are removed, and template fields and an opt-in inline Python function are new.

### Template fields

A schema can declare that a field's value is evaluated later, by the program, with values it supplies:

```python
schema = {
    "type": "dict",
    "required_keys": {
        "title": {
            "type": "template",
            "schema": {"type": "string"},
            "parameters": ["name"],
        }
    },
}
result = resolve({"title": {"__template__": "Homework ${ name }"}}, schema)
result["title"].evaluate({"name": "01"})  # "Homework 01"
```

When the configuration is resolved:

- A template field's value must be wrapped in `__template__`; it resolves to a `Template` holding the value as written.
- The value's structure is checked against the template's schema (dicts, lists, required keys), but `${ ... }` strings are not evaluated.
- `__use__` on a template field, or anywhere inside a template's value, is expanded now. Its target must be a template.
- Templates don't nest: a template field inside a template's value is an error, and so is a template schema whose inner schema is a template. (Allowed from 0.6.1.)

When the program calls `Template.evaluate(parameters)`:

- The value is evaluated against its schema, with the same converters, functions, filters, global variables and options as the original `resolve()` call. A parameter wins over a global of the same name.
- The keys must be exactly the template's parameters: a missing or an extra one is a `ResolutionError`.
- A top-level key of the template's value named like a parameter is an error, since the two would be ambiguous.
- Errors report keypaths relative to where the template was written.

### Inline Python

`smartconfig.stdlib.python.python` runs a string of Python code from the configuration as the body of a function of `args` (the call's `FunctionArgs`), and uses what it returns as the value:

```python
from smartconfig.stdlib.python import python

functions = {**smartconfig.DEFAULT_FUNCTIONS, "python": python}
config = {
    "start": "2025-10-01",
    "end": {"__python__": """
        import datetime
        return args.root["start"] + datetime.timedelta(weeks=10)
    """},
}
```

- It runs arbitrary code, so it is **not** a default function: it works only when passed to `resolve()`.
- Other values are read with `args.root`, already resolved to their types.
- Neither the code nor its result is interpolated; the result is converted to the field's schema. Returning `args.resolve(...)` opts into interpolation.
- The code is dedented first, so it can be written indented (in a triple-quoted string, say).
- A body with no `return` of its own, a body that uses `yield`, an empty body, a non-string input and invalid Python are errors, reported at the call (a syntax error with its line in the body). An exception raised by the code is a `ResolutionError` at the call, with the original as its `__cause__`; a `ResolutionError` raised inside (from `args.root`, say) keeps its own keypath.

### Breaking changes

Templates and the API:

- `__template__` always gives a `Template`. Before, it gave the dict `{"__template__": ...}`. On an `any` field it gives a `Template` with schema `any` and no parameters; on any other non-template field it's an `UnexpectedTemplateError`.
- The target of `__use__` must be a template. Its overrides are merged into the template's value as written, and a template written as a function call is rejected.
- **Prototypes are removed.** Schemas are the only way to describe a configuration. `Prototype`, `NotRequired` and `is_prototype_class` are gone.
- `Template` lives at `smartconfig.types.Template`; there is no top-level `smartconfig.Template`.
- `Template.evaluate`'s argument is named `parameters` (it was `variables`), like the schema's `"parameters"` and `Template.parameters`. Calls that pass it by keyword need the new name.
- `StrictUndefined` is no longer exported.
- `smartconfig.STDLIB_FUNCTIONS` is now `smartconfig.stdlib.DEFAULT_FUNCTIONS` (the stdlib functions on by default, as opposed to `python`), and is not exported at the top level. `smartconfig.DEFAULT_FUNCTIONS` is unchanged.
- `"any"` is no longer in `DEFAULT_CONVERTERS`: values of type `any` are never converted, and a custom `"any"` converter is ignored.

Schemas and inputs that used to be accepted:

- `resolve()` now validates a static schema before using it (dynamic schemas when they are called). A value type must name a converter; `nullable` must be a bool; a key can't be both required and optional; `required_keys`, `optional_keys` and the like must be well formed. A schema must be a mapping: a list of pairs used to pass validation and then crash `resolve()`. A `default` on the `element_schema` of an optional list is an error (it was accepted and ignored, since a list element can't be missing).
- Configuration keys must be strings (YAML reads `2: x` as the integer key 2).
- Unknown keys in the input of `__let__`, `datetime.at`, `datetime.offset` and `datetime.first` are errors, as are an unknown `__let__` reference target, a dynamic default on a required key, and `Template(parameters="abc")`.
- Names that `${ ... }` could never refer to are rejected wherever a name is introduced: `true`, `false` and `none` in either case, `not` and `self`. Global variables and `inject_root_as` raise `ValueError`; `__let__` names, template parameters and the `variable` of `list.loop` and `list.filter` are errors too. Configuration keys with these names are still allowed (reach them as `${ parent.true }`).

Interpolation:

- A `${ ... }` whose value is `None` is an error, rather than inserting the string `"None"`. Use `__splice__` to copy the `None`, or a default as in `${ x or '' }`.
- `${ self }` is an error (it used to insert `<TemplateReference None>`).
- A configuration dict or list turned into text inside `${ ... }`, as in `${ d | string }` or `${ 'x' ~ d }`, gives the text of the value it resolves to; it used to insert `<smartconfig._internals._UnresolvedDict object at 0x...>`. Inserting a container directly, `${ d }`, is still an error.
- A string with no `${`, `{%` or `{#` is kept exactly as written; before, Jinja changed line endings and dropped a trailing newline.
- An exception raised by an expression, a filter or a function is a `ResolutionError` at the keypath, with the original as its `__cause__`. A tree too deep to resolve is a `ResolutionError` rather than a `RecursionError`.

Dates:

- `datetime.offset`, `datetime.first` and `datetime.parse` keep dates as dates. A date offset by whole days, the first weekday after a date, and a parsed date with no time are dates; an offset in hours, `" at HH:MM"`, `datetime.at` or a datetime reference give a datetime. A date-only result in a `datetime` field is therefore a `ConversionError` ("Please include a time component"), as a date string already was. Add a time, as in `"3 days after ${ start } at 23:59"`.
- A unit repeated in a string offset, as in `"1 day, 2 days after 2021-10-05"`, is an error. Before, the later amount silently replaced the earlier one (giving Oct 7).

Functions:

- A function's result is resolved once. `Function(resolve_output=False)` (and `Function.new(resolve_output=False)`) marks a function whose result is already resolved; the stdlib list and dict functions use it, so a string they return is no longer interpolated a second time.

### Fixes

- `__if__` evaluates only the chosen branch.
- An error in a referenced value is reported as itself, at its own keypath, rather than as "keypath does not exist" or a circular reference.
- `preserve_type` works with function calls and keeps keys filled in by defaults.
- Internal containers no longer leak into the resolved output.
- In expressions, dicts and lists from the configuration behave like dicts and lists: `in`, negative indices, slices and `tojson` work. A key named like a container method (`keys`, `values`) is found as a key.
- Integer arguments of stdlib functions can be written as `${ ... }` references.
- In expressions, a list from the configuration equals the list it resolves to (`${ l == [3, 1, 2] }` was always `False`), and so does a dict that holds one.
- `datetime.at` and `parse`'s `" at ..."` keep the date's time zone; `parse` accepts `" at 9:00"` and units in any case.
- `datetime.parse` handles a date out of range and `"first , after ..."` as `offset` and `first` do; an offset out of range is a clear error.
- `__previous__` works in a `__let__` wrapped in another call.
- Everything under `__raw__` is data, in template fields too. A function call under `__raw__` as a template field's value used to run (so a `__use__` there reported its existing target as missing); it is now a dict, which gets the usual "expects a template" error. A `__use__` under `__raw__` inside a template's value is kept as written instead of being expanded at load. The docs now say that `__raw__` keeps function calls as data, not only `${ ... }`.
- `__use__` follows an enclosing `__fully_resolve__`, as `__if__` and `__let__` do; it used to resolve its copy with a single pass.
- Names in the input of a function call at the root no longer resolve as circular references, and neither does a `__splice__` evaluated while a root function call runs (in an `__if__`'s `then`, say); it says there is nothing to copy from yet.
- `list.filter` with a non-string `variable` is a `ResolutionError` (it was a bare `AssertionError`), and an error in its condition is reported at the element, as in `list.loop`.
- A number too large for a `float` field is a `ConversionError`: an int used to raise a raw `OverflowError`, and a numeric string silently became infinity. A string that spells infinity (`"inf"`) is still accepted.
- Errors in a dynamic schema are reported at its keypath wherever it is used (a list element, an extra key or an optional key used to report `type`). A dynamic schema that returns another dynamic schema is an `InvalidSchemaError`, and an exception it raises is a `ResolutionError` with the original as its `__cause__`.
- A name in `${ ... }` is resolved only if the expression uses it: in `${ y if debug else 'plain' }`, `y` is no longer resolved when `debug` is false, so it can't give a false "Circular reference". `${ y is defined }` and `${ y | default(1) }` still raise an error in `y`'s value rather than hiding it.
- Clearer messages and keypaths throughout: undefined names suggest a close match or list the names available; `${ ... }` where a dict or list is expected says that it always gives a string; inserting a `Template` says to use `__use__`.
- Resolving is about twice as fast: building each node no longer creates a class.

## Earlier versions

Releases before 0.6.0 have no changelog; see the git history and tags.
