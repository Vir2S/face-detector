# Coding Standards and Conventions

## Overview
This document outlines the coding standards for this project to ensure consistency, readability, and maintainability.

## Key Tools
- Dependency management: `uv`
- Linting and formatting: `black` or `ruff` (with format enabled)

## Formatting
- Line length: `120 characters`
- Use `ruff format .` or `black .` for all code.

## Typing
- 100% type annotations required.
- Use pyright in strict mode.

## Naming Conventions
- Variables/functions: `snake_case`
- Classes: `CamelCase`
- Class attributes: `snake_case`
- Class methods: `snake_case`
- Constants: `UPPER_CASE`

## Imports
- Sorted by ruff (isort profile).
- No wildcard imports.

## Documentation
- `Google-style` docstrings for all public functions/classes.

## Testing
- pytest with `>=85% coverage`.
- Fixtures in `conftest.py`.

## Forbidden Practices
- Mutable default arguments.
- eval/exec.
- Global variables.

For full config, see `pyproject.toml` and `.pre-commit-config.yaml`.