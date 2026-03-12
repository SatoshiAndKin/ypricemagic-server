# User Testing

Testing surface: tools, URLs, setup steps, known quirks.

---

- This is a code refactoring mission — no running server needed for validation
- All validation is done via test suite and grep-based checks
- Test command: `uv run pytest src/tests/ -x -q`
- Lint command: `uv run ruff check src/`
