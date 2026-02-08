- [x] allow "first" to accept a comma-separated list of weekdays
- [x] check that this way of using "first" is robust to spaces
- [x] do the same for the parsed "by" argument in "offset"
- [x] implement "parse" function
- [x] implement "at" function
    - check that it work with a datetime and overrides the time portion
- [x] implement an "except" function or parameter to exclude specific dates
- [x] add a test of time offset + except
- [x] rename "except" to "skip"?
- [x] Use types.KeyPath instead of tuple[str, ...]
- [x] better name than "parse_reference"?
- [x] more accurate helper function names (_parse? often not given a string)
- [x] Add "override" argument to "use" function
    - simple signature is just a keypath
    - advanced signature is a dict that contains keypath and overrides
- [x] STDLIB_FUNCTIONS should be namespaced
- [x] remove smartdatetime/smartdate converters
- [x] remove arithmetic converters? jinja can do this
- [x] clean up exported top-level functions in stdlib; export only the dicts
- [x] type checker passing? review all places where type checker is disabled
- [x] fuzz testing
- [x] does Claude see any other needed functions?
- [ ] review resolve module's docstring to see if it is up to date
- [ ] update documentation

## Codebase Reading List

### Source (suggested order)

- [x] `src/smartconfig/__init__.py` — Public API surface
- [x] `src/smartconfig/types.py` — Type definitions and protocols
- [x] `src/smartconfig/exceptions.py` — Error hierarchy
- [x] `src/smartconfig/_resolve.py` — Core resolution engine
- [x] `src/smartconfig/_core_functions.py` — Core functions (splice, raw, use, let, if, etc.)
- [x] `src/smartconfig/_utils.py` — Utility helpers
- [x] `src/smartconfig/_prototypes.py` — Prototype classes
- [x] `src/smartconfig/_schemas.py` — Schema validation
- [x] `src/smartconfig/converters.py` — Type converters
- [x] `src/smartconfig/stdlib/__init__.py` — Stdlib package init
- [ ] `src/smartconfig/stdlib/dict.py` — Stdlib dict functions
- [ ] `src/smartconfig/stdlib/list.py` — Stdlib list functions
- [ ] `src/smartconfig/stdlib/datetime.py` — Stdlib datetime functions

### Tests

- [ ] `tests/test_resolve/test_basic_resolution.py`
- [ ] `tests/test_resolve/test_interpolation.py`
- [ ] `tests/test_resolve/test_type_conversion.py`
- [ ] `tests/test_resolve/test_function_calls.py`
- [ ] `tests/test_resolve/test_any_type.py`
- [ ] `tests/test_resolve/test_nullable.py`
- [ ] `tests/test_resolve/test_global_variables.py`
- [ ] `tests/test_resolve/test_filters.py`
- [ ] `tests/test_resolve/test_dynamic_schemas.py`
- [ ] `tests/test_resolve/test_unresolved_containers.py`
- [ ] `tests/test_resolve/test_prototype_resolution.py`
- [ ] `tests/test_resolve/test_inject_root.py`
- [ ] `tests/test_resolve/test_error_messages.py`
- [ ] `tests/test_core_functions.py`
- [ ] `tests/test_converters.py`
- [ ] `tests/test_validate_schema.py`
- [ ] `tests/test_jinja.py`
- [ ] `tests/test_prototypes/test_definition.py`
- [ ] `tests/test_prototypes/test_init.py`
- [ ] `tests/test_prototypes/test_from_dict.py`
- [ ] `tests/test_prototypes/test_as_dict.py`
- [ ] `tests/test_prototypes/test_round_trip.py`
- [ ] `tests/test_prototypes/test_equality.py`
- [ ] `tests/test_prototypes/test_repr.py`
- [ ] `tests/test_prototypes/test_schema.py`
- [ ] `tests/test_prototypes/test_is_prototype_class.py`
- [ ] `tests/test_stdlib/test_dict.py`
- [ ] `tests/test_stdlib/test_list.py`
- [ ] `tests/test_stdlib/test_datetime.py`
