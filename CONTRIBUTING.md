# Contributing

## Setup
1. Create a virtual environment.
2. Install package in editable mode:
   - `pip install -e .`
3. Optional extras:
   - `pip install -e .[pdf]`
   - `pip install -e .[compression]`

## Development
- Keep cleaning deterministic.
- Preserve document structure and auditability.
- Add or update tests for behavior changes.

## Tests
- Run: `pytest -q`

## Pull Requests
- Keep PRs focused and small.
- Include tests and update docs when behavior changes.
- Ensure CI passes.
