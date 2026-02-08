# CLAUDE.md

## Project Overview

**smartconfig** is a Python library that extends standard configuration formats (JSON, YAML, TOML) with "smart" features: string interpolation (`${...}` syntax), function calls, Jinja2 templating, and type validation.

- **Docs**: https://eldridgejm.github.io/smartconfig/

## Development Commands

```bash
# Run all checks (lint, type check, tests, doctests, coverage)
uv run make checks

# Run tests
uv run pytest                      # All tests
uv run pytest -v                   # Verbose
uv run pytest --cov=src tests/     # With coverage

# Lint and format
uv run ruff check src tests        # Lint
uv run ruff format src tests       # Format
uv run ruff check --fix src tests  # Auto-fix

# Build documentation
cd docs && uv run make html        # Build HTML docs
cd docs && uv run make doctest     # Run doctests
```

## Project Structure

```
src/smartconfig/
├── __init__.py            # Public API: resolve(), DEFAULT_FUNCTIONS, DEFAULT_CONVERTERS
├── _resolve.py            # resolve() function, defaults, function flattening
├── _internals.py          # Node types, unresolved containers, make_node() (see docstring)
├── _core_functions.py     # Core functions: if, let, raw, resolve, fully_resolve, splice, use
├── _prototypes.py         # Prototype class-based schemas
├── _schemas.py            # Schema validation
├── _utils.py              # Shared utilities (deep_update)
├── converters.py          # Type converters (int, float, bool, date, datetime)
├── types.py               # Type definitions and protocols
├── exceptions.py          # Error, InvalidSchemaError, ResolutionError, ConversionError
└── stdlib/                # Namespaced built-in functions
    ├── __init__.py         # STDLIB_FUNCTIONS aggregation
    ├── datetime.py         # datetime.at, datetime.offset, datetime.first, datetime.parse
    ├── dict.py             # dict.update, dict.update_shallow, dict.from_items
    └── list.py             # list.loop, list.concatenate, list.filter, list.range, list.zip

tests/
├── test_converters.py          # Converter tests
├── test_core_functions.py      # Core function tests
├── test_jinja.py               # Jinja2 integration tests
├── test_validate_schema.py     # Schema validation tests
├── test_prototypes/            # Prototype tests
├── test_resolve/               # Resolution tests
└── test_stdlib/                # Stdlib function tests
```

## Architecture

1. **Tree-Based Processing**: Configurations become typed node trees (`_DictNode`, `_ListNode`, `_ValueNode`, `_FunctionCallNode`) defined in `_internals.py`
2. **Lazy Evaluation**: Unresolved containers (`_UnresolvedDict`, `_UnresolvedList`) defer computation until accessed
3. **Three-Phase Pipeline**: Build tree → Interpolate strings (Jinja2) → Convert types
4. **Schema-Driven**: Schemas guide structure validation and type conversion
5. **Functions**: Core functions (control flow, splicing) in `_core_functions.py`; stdlib functions (datetime, list, dict) namespaced under `stdlib/`

## Key Conventions

- **Private modules**: Implementation files prefixed with `_` (e.g., `_resolve.py`, `_internals.py`)
- **Public API**: All exports defined in `__init__.py`
- **Error context**: All errors include keypaths for debugging (e.g., `"foo.bar.baz"`)
- **Pre-commit**: Uses ruff for linting/formatting via `.pre-commit-config.yaml`
- **Docstrings**: NumPy style (Parameters, Returns, Raises sections)
- **Type aliases**: Use PEP 695 `type` statements (e.g., `type Foo = int | str`)
- **Union types**: Use `X | Y` syntax, not `Union[X, Y]`

## Key Dependencies

- **jinja2**: String templating for `${...}` interpolation
- **pytest**: Testing framework
- **ruff**: Linter and formatter
- **sphinx**: Documentation (RST format)

## Entry Points for Understanding Code

1. `src/smartconfig/__init__.py` - Public API surface
2. `src/smartconfig/_internals.py` - Internal tree representation (extensive docstring explains the full resolution algorithm)
3. `src/smartconfig/_resolve.py` - Public `resolve()` function and defaults
4. `tests/test_resolve/` - Best examples of usage patterns
