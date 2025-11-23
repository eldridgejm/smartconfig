# CLAUDE.md

## Project Overview

**smartconfig** is a Python library that extends standard configuration formats (JSON, YAML, TOML) with "smart" features: string interpolation (`${...}` syntax), natural language parsing (dates, arithmetic), function calls, Jinja2 templating, and type validation.

- **Docs**: https://eldridgejm.github.io/smartconfig/

## Development Commands

```bash
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
├── __init__.py       # Public API: resolve(), validate_schema(), DEFAULT_*
├── _resolve.py       # Core resolution engine (main logic)
├── _schemas.py       # Schema validation
├── converters.py     # Type converters (arithmetic, smartdate, smartdatetime, logic)
├── functions.py      # Built-in functions (if_, loop, let, filter_, etc.)
├── types.py          # Type definitions and protocols
└── exceptions.py     # Error, InvalidSchemaError, ResolutionError, ConversionError

tests/
├── test_resolve.py        # Core resolution tests (95 tests)
├── test_functions.py      # Function tests (72 tests)
├── test_converters.py     # Converter tests (44 tests)
├── test_validate_schema.py # Schema tests (14 tests)
└── test_jinja.py          # Jinja2 tests (8 tests)
```

## Architecture

1. **Tree-Based Processing**: Configurations become typed node trees (`_DictNode`, `_ListNode`, `_ValueNode`, `_FunctionCallNode`)
2. **Lazy Evaluation**: Unresolved containers (`_UnresolvedDict`, `_UnresolvedList`) defer computation until accessed
3. **Three-Phase Pipeline**: Build tree → Interpolate strings (Jinja2) → Convert types
4. **Schema-Driven**: Schemas guide structure validation and type conversion

## Key Conventions

- **Private modules**: Implementation files prefixed with `_` (e.g., `_resolve.py`)
- **Public API**: All exports defined in `__init__.py`
- **Error context**: All errors include keypaths for debugging (e.g., `"foo.bar.baz"`)
- **Pre-commit**: Uses ruff for linting/formatting via `.pre-commit-config.yaml`
- **Docstrings**: NumPy style (Parameters, Returns, Raises sections)

## Key Dependencies

- **jinja2**: String templating for `${...}` interpolation
- **pytest**: Testing framework
- **ruff**: Linter and formatter
- **sphinx**: Documentation (RST format)

## Entry Points for Understanding Code

1. `src/smartconfig/__init__.py` - Public API surface
2. `src/smartconfig/_resolve.py` - Core resolution logic (lines 1-210 have excellent docstring)
3. `tests/test_resolve.py` - Best examples of usage patterns
